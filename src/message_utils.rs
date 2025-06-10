use crate::{crypto_utils::CryptoUtils, db_utils::DbUtils};
use nym_sdk::mixnet::{AnonymousSenderTag, MixnetClientSender, MixnetMessageSender, ReconstructedMessage};
use serde_json::{Value, json};
use std::collections::HashMap;
use uuid::Uuid;

/// Handler for incoming mixnet messages and command processing.
pub struct MessageUtils {
    db: DbUtils,
    crypto: CryptoUtils,
    sender: MixnetClientSender,
    client_id: String,
    pending_users: HashMap<AnonymousSenderTag, (String, String, String)>,
    nonces: HashMap<AnonymousSenderTag, (String, String, String)>,
}

impl MessageUtils {
    /// Create a new MessageUtils instance.
    pub fn new(
        client_id: String,
        sender: MixnetClientSender,
        db: DbUtils,
        crypto: CryptoUtils,
    ) -> Self {
        MessageUtils {
            sender,
            db,
            crypto,
            client_id,
            pending_users: HashMap::new(),
            nonces: HashMap::new(),
        }
    }

    /// Check if a username is valid: only alphanumeric, '-' or '_'.
    fn is_valid_username(username: &str) -> bool {
        !username.is_empty()
            && username
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
    }

    /// Process an incoming mixnet message.
    pub async fn process_received_message(&mut self, msg: ReconstructedMessage) {
        let sender_tag = if let Some(tag) = msg.sender_tag {
            tag
        } else {
            log::warn!("Received message without sender tag, ignoring");
            return;
        };
        let raw = match String::from_utf8(msg.message) {
            Ok(s) => s,
            Err(e) => {
                log::error!("Invalid UTF-8 in message: {}", e);
                return;
            }
        };
        let data: Value = match serde_json::from_str(&raw) {
            Ok(v) => v,
            Err(e) => {
                log::error!("processReceivedMessage - JSON decode error: {}", e);
                return;
            }
        };
        if let Some(action) = data.get("action").and_then(Value::as_str) {
            match action {
                "query" => self.handle_query(&data, sender_tag).await,
                "register" => self.handle_register(&data, sender_tag).await,
                "registrationResponse" => {
                    self.handle_registration_response(&data, sender_tag).await
                }
                "login" => self.handle_login(&data, sender_tag).await,
                "loginResponse" => self.handle_login_response(&data, sender_tag).await,
                "update" => self.handle_update(&data, sender_tag).await,
                "send" => self.handle_send(&data, sender_tag).await,
                "sendGroup" => self.handle_send_group(&data, sender_tag).await,
                "createGroup" => self.handle_create_group(&data, sender_tag).await,
                "inviteGroup" => self.handle_send_invite(&data, sender_tag).await,
                _ => log::error!("Unknown action: {}", action),
            }
        } else {
            log::error!("processReceivedMessage - missing action field");
        }
    }

    async fn handle_query(&mut self, data: &Value, sender_tag: AnonymousSenderTag) {
        if let Some(username) = data.get("username").and_then(Value::as_str) {
        match self.db.get_user_by_username(username).await.unwrap_or(None) {
            Some((user, pubkey, _)) => {
                let reply = json!({"username": user, "publicKey": pubkey}).to_string();
                self.send_encapsulated_reply(sender_tag, reply, "queryResponse", Some("query")).await;
            }
            None => {
                self.send_encapsulated_reply(
                    sender_tag,
                    "No user found".into(),
                    "queryResponse",
                    Some("query"),
                )
                .await;
            }
        }
        } else {
            self.send_encapsulated_reply(
                sender_tag,
                "error: missing 'username' field".into(),
                "queryResponse",
                Some("query"),
            )
            .await;
        }
    }

    async fn handle_register(&mut self, data: &Value, sender_tag: AnonymousSenderTag) {
        let usernym = data.get("usernym").and_then(Value::as_str);
        let public_key = data.get("publicKey").and_then(Value::as_str);
        if usernym.is_none() || public_key.is_none() {
            self.send_encapsulated_reply(
                sender_tag,
                "error: missing username or public key".into(),
                "challengeResponse",
                Some("registration"),
            )
            .await;
            return;
        }
        let username = usernym.unwrap();
        let pubkey = public_key.unwrap();
        if !Self::is_valid_username(username) {
            self.send_encapsulated_reply(
                sender_tag,
                "error: invalid username format".into(),
                "challengeResponse",
                Some("registration"),
            )
            .await;
            return;
        }
        if self
            .db
            .get_user_by_username(username)
            .await
            .unwrap_or(None)
            .is_some()
        {
            self.send_encapsulated_reply(
                sender_tag,
                "error: username already in use".into(),
                "challengeResponse",
                Some("registration"),
            )
            .await;
            return;
        }
        let nonce = Uuid::new_v4().to_string();
        self.pending_users.insert(
            sender_tag,
            (username.to_string(), pubkey.to_string(), nonce.clone()),
        );
        self.send_encapsulated_reply(
            sender_tag,
            json!({"nonce": nonce}).to_string(),
            "challenge",
            Some("registration"),
        )
        .await;
    }

    async fn handle_registration_response(&mut self, data: &Value, sender_tag: AnonymousSenderTag) {
        let signature = data.get("signature").and_then(Value::as_str);
        if signature.is_none() {
            self.send_encapsulated_reply(
                sender_tag,
                "error: missing signature".into(),
                "challengeResponse",
                Some("registration"),
            )
            .await;
            return;
        }
        let signature = signature.unwrap();
        if let Some((username, pubkey, nonce)) = self.pending_users.remove(&sender_tag) {
            if self.crypto.verify_signature(&pubkey, &nonce, signature) {
            if self
                .db
                .add_user(&username, &pubkey, &sender_tag.to_string())
                .await
                .unwrap_or(false)
            {
                self.send_encapsulated_reply(
                    sender_tag,
                    "success".into(),
                    "challengeResponse",
                    Some("registration"),
                )
                .await;
            } else {
                self.send_encapsulated_reply(
                    sender_tag,
                    "error: database failure".into(),
                    "challengeResponse",
                    Some("registration"),
                )
                .await;
            }
            } else {
                self.send_encapsulated_reply(
                    sender_tag,
                    "error: signature verification failed".into(),
                    "challengeResponse",
                    Some("registration"),
                )
                .await;
            }
        } else {
            self.send_encapsulated_reply(
                sender_tag,
                "error: no pending registration".into(),
                "challengeResponse",
                Some("registration"),
            )
            .await;
        }
    }

    async fn handle_login(&mut self, data: &Value, sender_tag: AnonymousSenderTag) {
        let username = data.get("usernym").and_then(Value::as_str);
        if username.is_none() {
            self.send_encapsulated_reply(
                sender_tag,
                "error: missing username".into(),
                "challengeResponse",
                Some("login"),
            )
            .await;
            return;
        }
        let username = username.unwrap();
        if let Some((_user, pubkey, _)) = self
            .db
            .get_user_by_username(username)
            .await
            .unwrap_or(None)
        {
            let nonce = Uuid::new_v4().to_string();
            self.nonces
                .insert(sender_tag, (username.to_string(), pubkey, nonce.clone()));
            self.send_encapsulated_reply(
                sender_tag,
                json!({"nonce": nonce}).to_string(),
                "challenge",
                Some("login"),
            )
            .await;
        } else {
            self.send_encapsulated_reply(
                sender_tag,
                "error: user not found".into(),
                "challengeResponse",
                Some("login"),
            )
            .await;
        }
    }

    async fn handle_login_response(&mut self, data: &Value, sender_tag: AnonymousSenderTag) {
        let signature = data.get("signature").and_then(Value::as_str);
        if signature.is_none() {
            self.send_encapsulated_reply(
                sender_tag,
                "error: missing signature".into(),
                "challengeResponse",
                Some("login"),
            )
            .await;
            return;
        }
        let signature = signature.unwrap();
        if let Some((username, pubkey, nonce)) = self.nonces.remove(&sender_tag) {
            if self.crypto.verify_signature(&pubkey, &nonce, signature) {
            if let Some((_u, _pk, db_sender_tag)) = self
                .db
                .get_user_by_username(&username)
                .await
                .unwrap_or(None)
            {
                if db_sender_tag != sender_tag.to_string() {
                    let _ = self
                        .db
                        .update_user_field(&username, "senderTag", &sender_tag.to_string())
                        .await;
                }
            }
                self.send_encapsulated_reply(
                    sender_tag,
                    "success".into(),
                    "challengeResponse",
                    Some("login"),
                )
                .await;
            } else {
                self.send_encapsulated_reply(
                    sender_tag,
                    "error: invalid signature".into(),
                    "challengeResponse",
                    Some("login"),
                )
                .await;
            }
        } else {
            self.send_encapsulated_reply(
                sender_tag,
                "error: no pending login".into(),
                "challengeResponse",
                Some("login"),
            )
            .await;
        }
    }

    async fn handle_send(&mut self, data: &Value, sender_tag: AnonymousSenderTag) {
        let content_str = data.get("content").and_then(Value::as_str);
        let signature = data.get("signature").and_then(Value::as_str);
        if content_str.is_none() || signature.is_none() {
            self.send_encapsulated_reply(
                sender_tag,
                "error: missing 'content' or 'signature'".into(),
                "sendResponse",
                Some("chat"),
            )
            .await;
            return;
        }
        let content_str = content_str.unwrap();
        let signature = signature.unwrap();
        let content: Value = match serde_json::from_str(content_str) {
            Ok(v) => v,
            Err(_) => {
                self.send_encapsulated_reply(
                    sender_tag,
                    "error: invalid JSON in content".into(),
                    "sendResponse",
                    Some("chat"),
                )
                .await;
                return;
            }
        };
        let sender_username = content.get("sender").and_then(Value::as_str);
        let recipient_username = content.get("recipient").and_then(Value::as_str);
        if sender_username.is_none() || recipient_username.is_none() {
            self.send_encapsulated_reply(
                sender_tag,
                "error: missing 'sender' or 'recipient' field".into(),
                "sendResponse",
                Some("chat"),
            )
            .await;
            return;
        }
        let sender_username = sender_username.unwrap();
        let recipient_username = recipient_username.unwrap();
        if let Some((_u, pubkey, db_sender_tag)) = self
            .db
            .get_user_by_username(sender_username)
            .await
            .unwrap_or(None)
        {
            if !self
                .crypto
                .verify_signature(&pubkey, content_str, signature)
            {
                self.send_encapsulated_reply(
                    sender_tag,
                    "error: invalid signature".into(),
                    "sendResponse",
                    Some("chat"),
                )
                .await;
                return;
            }
            if db_sender_tag != sender_tag.to_string() {
                let _ = self
                    .db
                    .update_user_field(sender_username, "senderTag", &sender_tag.to_string())
                    .await;
            }
        } else {
            self.send_encapsulated_reply(
                sender_tag,
                "error: unrecognized sender username".into(),
                "sendResponse",
                Some("chat"),
            )
            .await;
            return;
        }
        if let Some((_u2, _pk2, target_sender_tag)) = self
            .db
            .get_user_by_username(recipient_username)
            .await
            .unwrap_or(None)
        {
            if let Ok(tag) = AnonymousSenderTag::try_from_base58_string(&target_sender_tag) {
                let mut forward = json!({"sender": sender_username, "body": content.get("body").cloned().unwrap_or(Value::Null)});
                if let Some(spk) = content.get("senderPublicKey") {
                    forward["senderPublicKey"] = spk.clone();
                }
                self.send_encapsulated_reply(
                    tag,
                    forward.to_string(),
                    "incomingMessage",
                    Some("chat"),
                )
                .await;
            }
            self.send_encapsulated_reply(
                sender_tag,
                "success".into(),
                "sendResponse",
                Some("chat"),
            )
            .await;
        } else {
            self.send_encapsulated_reply(
                sender_tag,
                "error: recipient not found".into(),
                "sendResponse",
                Some("chat"),
            )
            .await;
        }
    }

    async fn handle_create_group(&mut self, _data: &Value, sender_tag: AnonymousSenderTag) {
        log::warn!("handleCreateGroup - stubs not implemented");
        self.send_encapsulated_reply(
            sender_tag,
            "error: unimplemented".into(),
            "createGroupResponse",
            None,
        )
        .await;
    }
    async fn handle_send_group(&mut self, _data: &Value, sender_tag: AnonymousSenderTag) {
        log::warn!("handleSendGroup - stubs not implemented");
        self.send_encapsulated_reply(
            sender_tag,
            "error: unimplemented".into(),
            "sendGroupResponse",
            None,
        )
        .await;
    }
    async fn handle_send_invite(&mut self, _data: &Value, sender_tag: AnonymousSenderTag) {
        log::warn!("handleSendInvite - stubs not implemented");
        self.send_encapsulated_reply(
            sender_tag,
            "error: unimplemented".into(),
            "inviteGroupResponse",
            None,
        )
        .await;
    }
    async fn handle_update(&mut self, _data: &Value, sender_tag: AnonymousSenderTag) {
        log::warn!("handleUpdate - stubs not implemented");
        self.send_encapsulated_reply(
            sender_tag,
            "error: unimplemented".into(),
            "updateResponse",
            None,
        )
        .await;
    }

    /// Sign and send a JSON reply over the mixnet using SURBs.
    async fn send_encapsulated_reply(
        &self,
        recipient: AnonymousSenderTag,
        content: String,
        action: &str,
        context: Option<&str>,
    ) {
        let mut payload = json!({"action": action, "content": content});
        if let Some(ctx) = context {
            payload["context"] = json!(ctx);
        }
        let to_sign = payload["content"].as_str().unwrap_or_default().to_string();
        if let Ok(signature) = self.crypto.sign_message(&self.client_id, &to_sign) {
            payload["signature"] = json!(signature);
            let msg = payload.to_string();
            let _ = self.sender.send_reply(recipient, msg).await;
        } else {
            log::error!("sendEncapsulatedReply - failed to sign message");
        }
    }
}
