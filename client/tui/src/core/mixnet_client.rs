//! Mixnet service: wraps nym-sdk client, crypto, and persistence
#![allow(dead_code)]
use crate::core::{crypto::Crypto, db::Db, messages::MixnetEnvelope};
use anyhow::{Context, Result, anyhow};
use chrono::Utc;
use nym_sdk::mixnet::{
    IncludedSurbs, MixnetClient, MixnetClientBuilder, MixnetClientSender, MixnetMessageSender,
    Recipient,
};
use serde_json;
use std::{collections::HashMap, env, sync::Arc};
use tokio::sync::{Mutex, mpsc};
use tokio_stream::StreamExt;

/// Incoming envelope from mixnet (server or peer)
pub struct Incoming {
    /// Decoded mixnet envelope
    pub envelope: MixnetEnvelope,
    /// Timestamp when received
    pub ts: chrono::DateTime<Utc>,
}

/// Service holding client, crypto, and DB
pub struct MixnetService {
    client: Arc<Mutex<Option<MixnetClient>>>,
    sender: MixnetClientSender,
    pub crypto: Crypto,
    pub db: Arc<Db>,
    nym_addresses: Arc<Mutex<HashMap<String, String>>>,
}

impl MixnetService {
    /// Create new service: opens DB, connects client, and spawns receive loop
    pub async fn new(db_path: &str) -> Result<(Self, mpsc::Receiver<Incoming>)> {
        // open database
        let db = Arc::new(Db::open(db_path).await?);
        db.init_global()?;
        // connect mixnet client
        let client = MixnetClientBuilder::new_ephemeral()
            .build()
            .context("Failed to build mixnet client")?
            .connect_to_mixnet()
            .await
            .context("Failed to connect to mixnet")?;
        let sender = client.split_sender();
        // wrap client in a mutex for shared access
        let client = Arc::new(Mutex::new(Some(client)));
        let service = Self {
            client: client.clone(),
            sender,
            crypto: Crypto,
            db: db.clone(),
            nym_addresses: Arc::new(Mutex::new(HashMap::new())),
        };
        // channel for incoming messages
        let (tx, rx) = mpsc::channel(100);
        // spawn receive loop: forward all envelopes to channel
        {
            let client_ref = client.clone();
            let tx = tx.clone();
            tokio::spawn(async move {
                let mut lock = client_ref.lock().await;
                if let Some(client) = lock.as_mut() {
                    while let Some(frame) = client.next().await {
                        if let Ok(text) = String::from_utf8(frame.message.clone()) {
                            if let Ok(env) = serde_json::from_str::<MixnetEnvelope>(&text) {
                                let incoming = Incoming {
                                    envelope: env,
                                    ts: Utc::now(),
                                };
                                if tx.send(incoming).await.is_err() {
                                    break;
                                }
                            }
                        }
                    }
                }
            });
        }
        Ok((service, rx))
    }

    /// Register a new user: generate keys, send registration envelope
    pub async fn register(&self, username: &str) -> Result<()> {
        // generate a new keypair (PEM private, PEM public)
        let (_private_pem, public_pem) =
            Crypto::generate_keypair().context("key generation failed")?;
        // public_pem is already PEM-encoded SubjectPublicKeyInfo
        let public_key = String::from_utf8(public_pem.clone())
            .map_err(|e| anyhow!(format!("PEM to UTF-8 error: {}", e)))?;
        // store user in database
        self.db.register_user(username, &public_key)?;
        // build registration envelope
        let env = MixnetEnvelope::register(username, &public_key);
        let inner = env.to_json()?;
        let raw_bytes = inner.into_bytes();
        // send via mixnet to server
        let server_addr = env::var("SERVER_ADDRESS").context("SERVER_ADDRESS must be set")?;
        let recipient: Recipient = server_addr.parse()?;
        self.sender
            .send_message(recipient, raw_bytes, IncludedSurbs::Amount(10))
            .await?;
        Ok(())
    }

    /// Login existing user: load keys, send login envelope
    pub async fn login(&self, username: &str) -> Result<()> {
        // build login envelope
        let env = MixnetEnvelope::login(username);
        let inner = env.to_json()?;
        let raw_bytes = inner.into_bytes();
        // send via mixnet to server
        let server_addr = env::var("SERVER_ADDRESS").context("SERVER_ADDRESS must be set")?;
        let recipient: Recipient = server_addr.parse()?;
        self.sender
            .send_message(recipient, raw_bytes, IncludedSurbs::Amount(10))
            .await?;
        Ok(())
    }

    /// Query for a user's public key via the server
    pub async fn query_user(&self, username: &str) -> Result<Option<(String, String)>> {
        // for now, lookup in local DB
        Ok(self.db.get_user(username)?)
    }

    /// Send a message via the central server with content and signature
    pub async fn send_message(&self, _to: &str, content: &str, signature: &str) -> Result<()> {
        // Build the envelope exactly as in the Python client
        let envelope = MixnetEnvelope::send(content, signature);
        let payload = envelope.to_json()?;
        let raw_bytes = payload.into_bytes();

        // Send those raw JSON bytes directly to the server
        let server_addr: String =
            std::env::var("SERVER_ADDRESS").context("SERVER_ADDRESS must be set")?;
        let recipient: Recipient = server_addr.parse()?;
        self.sender
            .send_message(recipient, raw_bytes, IncludedSurbs::Amount(10))
            .await?;

        Ok(())
    }

    /// Send a p2p direct chat message with content and signature
    pub async fn send_direct_message(
        &self,
        _to: &str,
        content: &str,
        signature: &str,
    ) -> Result<()> {
        // Build the direct message envelope as expected by receiving clients
        let env = MixnetEnvelope::direct_message(content, signature);
        let inner = env.to_json()?;
        let raw_bytes = inner.into_bytes();
        // Route via central server (or override if direct address is known)
        let server_addr = env::var("SERVER_ADDRESS").context("SERVER_ADDRESS must be set")?;
        let recipient: Recipient = server_addr.parse()?;
        self.sender
            .send_message(recipient, raw_bytes, IncludedSurbs::Amount(10))
            .await?;
        Ok(())
    }

    /// Send handshake (type=1) to establish anonymous replies
    pub async fn send_handshake(&self, _to: &str) -> Result<()> {
        // send a handshake via server (stub)
        let env = MixnetEnvelope::send("handshake", "");
        let inner = env.to_json()?;
        let raw_bytes = inner.into_bytes();
        let server_addr = env::var("SERVER_ADDRESS").context("SERVER_ADDRESS must be set")?;
        let recipient: Recipient = server_addr.parse()?;
        self.sender
            .send_message(recipient, raw_bytes, IncludedSurbs::Amount(10))
            .await?;
        Ok(())
    }
    /// Send a registration request with username and public key
    pub async fn send_registration_request(&self, username: &str, public_key: &str) -> Result<()> {
        let env = MixnetEnvelope::register(username, public_key);
        let inner = env.to_json()?;
        let raw_bytes = inner.into_bytes();
        let server_addr = env::var("SERVER_ADDRESS").context("SERVER_ADDRESS must be set")?;
        let recipient: Recipient = server_addr.parse()?;
        self.sender
            .send_message(recipient, raw_bytes, IncludedSurbs::Amount(10))
            .await?;
        Ok(())
    }
    /// Send registration challenge response
    pub async fn send_registration_response(&self, username: &str, signature: &str) -> Result<()> {
        let env = MixnetEnvelope::registration_response(username, signature);
        let inner = env.to_json()?;
        let raw_bytes = inner.into_bytes();
        let server_addr = env::var("SERVER_ADDRESS").context("SERVER_ADDRESS must be set")?;
        let recipient: Recipient = server_addr.parse()?;
        self.sender
            .send_message(recipient, raw_bytes, IncludedSurbs::Amount(10))
            .await?;
        Ok(())
    }
    /// Send a login request for a username
    pub async fn send_login_request(&self, username: &str) -> Result<()> {
        let env = MixnetEnvelope::login(username);
        let inner = env.to_json()?;
        let raw_bytes = inner.into_bytes();
        let server_addr = env::var("SERVER_ADDRESS").context("SERVER_ADDRESS must be set")?;
        let recipient: Recipient = server_addr.parse()?;
        self.sender
            .send_message(recipient, raw_bytes, IncludedSurbs::Amount(10))
            .await?;
        Ok(())
    }
    /// Send login challenge response
    pub async fn send_login_response(&self, username: &str, signature: &str) -> Result<()> {
        let env = MixnetEnvelope::login_response(username, signature);
        let inner = env.to_json()?;
        let raw_bytes = inner.into_bytes();
        let server_addr = env::var("SERVER_ADDRESS").context("SERVER_ADDRESS must be set")?;
        let recipient: Recipient = server_addr.parse()?;
        self.sender
            .send_message(recipient, raw_bytes, IncludedSurbs::Amount(10))
            .await?;
        Ok(())
    }
    /// Send a query request for a user's public key
    pub async fn send_query_request(&self, username: &str) -> Result<()> {
        let env = MixnetEnvelope::query(username);
        let inner = env.to_json()?;
        let raw_bytes = inner.into_bytes();
        let server_addr = env::var("SERVER_ADDRESS").context("SERVER_ADDRESS must be set")?;
        let recipient: Recipient = server_addr.parse()?;
        self.sender
            .send_message(recipient, raw_bytes, IncludedSurbs::Amount(10))
            .await?;
        Ok(())
    }
}

// Allow cloning service for spawn
impl Clone for MixnetService {
    fn clone(&self) -> Self {
        Self {
            client: Arc::clone(&self.client),
            sender: self.sender.clone(),
            crypto: Crypto,
            db: self.db.clone(),
            nym_addresses: Arc::clone(&self.nym_addresses),
        }
    }
}
