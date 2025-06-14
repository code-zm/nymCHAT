//! High-level handler for user registration, login, messaging, and queries
#![allow(dead_code)]
use crate::core::crypto::Crypto;
use crate::core::db::Db;
use crate::core::mixnet_client::{Incoming, MixnetService};
use anyhow::anyhow;
use chrono::Utc;
use hex;
use log::info;
use serde_json::Value;
use tokio::sync::mpsc::Receiver;

/// Handles user state, persistence, and mixnet interactions
pub struct MessageHandler {
    /// Crypto utilities
    pub crypto: Crypto,
    /// Underlying mixnet service client
    pub service: MixnetService,
    /// Incoming message receiver
    pub incoming_rx: Receiver<Incoming>,
    /// Database for persistence
    pub db: Db,
    /// Currently logged-in username
    pub current_user: Option<String>,
    /// Our own nym address
    pub nym_address: Option<String>,
    /// Optional user's private key PKCS#8 DER for signing and decryption
    pub private_key: Option<Vec<u8>>,
    /// Optional user's public key SPKI DER for encryption and verification
    pub public_key: Option<Vec<u8>>,
}

impl MessageHandler {
    /// Create a new handler by wrapping the mixnet service and DB
    pub async fn new(
        service: MixnetService,
        incoming_rx: Receiver<Incoming>,
        db_path: &str,
    ) -> anyhow::Result<Self> {
        let db = Db::open(db_path).await?;
        db.init_global().await?;
        Ok(Self {
            crypto: Crypto,
            service,
            incoming_rx,
            db,
            current_user: None,
            nym_address: None,
            private_key: None,
            public_key: None,
        })
    }

    /// Register a new user via the mixnet service, awaiting server responses
    pub async fn register_user(&mut self, username: &str) -> anyhow::Result<bool> {
        // Generate keypair (PEM-encoded private & public keys)
        let (sk_pem, pub_pem) = Crypto::generate_keypair()?;
        // Store keys in handler for signing/encryption
        self.private_key = Some(sk_pem.clone());
        self.public_key = Some(pub_pem.clone());
        // Convert public key PEM to UTF-8 string
        let public_key_pem = String::from_utf8(pub_pem.clone())?;
        // Persist and send the public key in PEM (SubjectPublicKeyInfo) format
        self.db.register_user(username, &public_key_pem).await?;
        self.service
            .send_registration_request(username, &public_key_pem)
            .await?;
        // Await server challenge and responses
        while let Some(incoming) = self.incoming_rx.recv().await {
            let env = incoming.envelope;
            // Handle challenge to sign
            if env.action == "challenge" && env.context.as_deref() == Some("registration") {
                if let Some(content) = env.content {
                    if let Ok(v) = serde_json::from_str::<Value>(&content) {
                        if let Some(nonce) = v.get("nonce").and_then(|n| n.as_str()) {
                            let sk = self.private_key.as_ref().unwrap();
                            let sig_bytes = Crypto::sign(sk, nonce.as_bytes())?;
                            let signature = hex::encode(&sig_bytes);
                            self.service
                                .send_registration_response(username, &signature)
                                .await?;
                        }
                    }
                }
            }
            // Final challenge response from server
            else if env.action == "challengeResponse"
                && env.context.as_deref() == Some("registration")
            {
                if let Some(result) = env.content {
                    if result == "success" {
                        // Registration succeeded
                        self.db.init_user(username).await?;
                        self.current_user = Some(username.to_string());
                        return Ok(true);
                    } else {
                        return Ok(false);
                    }
                }
            }
        }
        Ok(false)
    }

    /// Login an existing user via the mixnet service, awaiting server response
    pub async fn login_user(&mut self, username: &str) -> anyhow::Result<bool> {
        // Ensure current user is set and private key is available
        self.current_user = Some(username.to_string());
        if self.private_key.is_none() {
            info!("No private key available for login of {}", username);
            return Ok(false);
        }

        // Send initial login request
        self.service.send_login_request(username).await?;
        // Await server challenge and responses
        while let Some(incoming) = self.incoming_rx.recv().await {
            let env = incoming.envelope;
            // Handle login challenge (nonce signing)
            if env.action == "challenge" && env.context.as_deref() == Some("login") {
                if let Some(content) = env.content {
                    if let Ok(v) = serde_json::from_str::<Value>(&content) {
                        if let Some(nonce) = v.get("nonce").and_then(|n| n.as_str()) {
                            let sk = self.private_key.as_ref().unwrap();
                            let sig_bytes = Crypto::sign(sk, nonce.as_bytes())?;
                            let signature = hex::encode(&sig_bytes);
                            self.service
                                .send_login_response(username, &signature)
                                .await?;
                        }
                    }
                }
            }
            // Handle final login response
            else if env.action == "challengeResponse" && env.context.as_deref() == Some("login") {
                if let Some(result) = env.content {
                if result == "success" {
                        self.db.init_user(username).await?;
                        self.current_user = Some(username.to_string());
                        return Ok(true);
                    } else {
                        return Ok(false);
                    }
                }
            }
        }
        Ok(false)
    }

    /// Query for a user's public key via the mixnet service, awaiting server response
    pub async fn query_user(&mut self, username: &str) -> anyhow::Result<Option<(String, String)>> {
        // Send query request
        self.service.send_query_request(username).await?;
        // Await server's query response
        while let Some(incoming) = self.incoming_rx.recv().await {
            let env = incoming.envelope;
            if env.action == "queryResponse" && env.context.as_deref() == Some("query") {
                if let Some(content) = env.content {
                    if let Ok(v) = serde_json::from_str::<Value>(&content) {
                        if let (Some(user), Some(pk)) = (
                            v.get("username").and_then(|u| u.as_str()),
                            v.get("publicKey").and_then(|k| k.as_str()),
                        ) {
                            let res = (user.to_string(), pk.to_string());
                            // Persist contact
                            if let Some(me) = &self.current_user {
                                let _ = self.db.add_contact(me, user, pk).await;
                            }
                            return Ok(Some(res));
                        }
                    }
                }
                return Ok(None);
            }
        }
        Ok(None)
    }

    /// Send a direct (encrypted) message to a contact
    pub async fn send_direct_message(&self, recipient: &str, text: &str) -> anyhow::Result<()> {
        // 1) Persist locally
        let sender = self.current_user.as_deref().unwrap_or("");
        self.db
            .save_message(sender, recipient, true, text, Utc::now())
            .await?;

        // 2) Build a JSON payload matching the Python client:
        //    { "sender": "<you>", "recipient": "<them>", "body": "<your text>" }
        let payload = serde_json::json!({
            "sender": sender,
            "recipient": recipient,
            "body": text
        });
        let payload_str = payload.to_string();

        // 3) Sign that entire JSON string
        let sk = self
            .private_key
            .as_ref()
            .ok_or_else(|| anyhow!("Missing private key"))?;
        let sig_bytes = Crypto::sign(sk, payload_str.as_bytes())?;
        let signature = hex::encode(sig_bytes);

        // 4) Send it exactly like Python does:
        //    content = payload_str (a valid JSON document)
        //    signature = outer signature over payload_str
        self.service
            .send_message(recipient, &payload_str, &signature)
            .await?;

        Ok(())
    }

    /// Send a handshake message
    pub async fn send_handshake(&self, recipient: &str) -> anyhow::Result<()> {
        self.service.send_handshake(recipient).await?;
        Ok(())
    }

    /// Drain incoming chat messages: returns Vec of (from, content)
    pub async fn drain_incoming(&mut self) -> Vec<(String, String)> {
        let mut msgs = Vec::new();
        while let Ok(incoming) = self.incoming_rx.try_recv() {
            let env = incoming.envelope;
            // Only handle chat messages
            if env.action == "incomingMessage" && env.context.as_deref() == Some("chat") {
                if let Some(content_str) = env.content {
                    // content_str is a JSON payload containing sender, body, etc.
                    if let Ok(payload) = serde_json::from_str::<Value>(&content_str) {
                        if let Some(sender) = payload.get("sender").and_then(|s| s.as_str()) {
                            // Extract ciphertext from encryptedPayload
                            let message = payload
                                .get("body")
                                .and_then(|b| b.get("encryptedPayload"))
                                .and_then(|e| e.get("ciphertext"))
                                .and_then(|c| c.as_str())
                                .unwrap_or(&content_str)
                                .to_string();
                            info!("Incoming from {}: {}", sender, message);
                            // Persist incoming
                            if let Some(user) = &self.current_user {
                                let _ = self.db.save_message(
                                    user,
                                    sender,
                                    false,
                                    &message,
                                    incoming.ts,
                                )
                                .await;
                            }
                            msgs.push((sender.to_string(), message));
                        }
                    }
                }
            }
        }
        msgs
    }
}
