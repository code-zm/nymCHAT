//! Definition and serialization of mixnet envelope messages
#![allow(dead_code)]
use anyhow::Result;
use serde::{Deserialize, Serialize};

/// Generic mixnet message envelope for server and p2p interactions
#[derive(Serialize, Deserialize, Debug)]
pub struct MixnetEnvelope {
    /// action to perform (e.g., "query", "send", etc.)
    pub action: String,
    /// for actions that include a username (e.g., query results, responses)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub username: Option<String>,
    /// for actions that include a usernym (e.g., register, login)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usernym: Option<String>,
    /// publicKey for register action
    #[serde(skip_serializing_if = "Option::is_none", rename = "publicKey")]
    pub public_key: Option<String>,
    /// field name for update action
    #[serde(skip_serializing_if = "Option::is_none")]
    pub field: Option<String>,
    /// value for update action
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<String>,
    /// content for send/directMessage/sendGroup actions
    #[serde(skip_serializing_if = "Option::is_none")]
    pub content: Option<String>,
    /// context for directMessage (e.g., "chat")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub context: Option<String>,
    /// cryptographic signature if present
    #[serde(skip_serializing_if = "Option::is_none")]
    pub signature: Option<String>,
    /// target for sendGroup or inviteGroup actions
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target: Option<String>,
    /// groupID for inviteGroup or sendGroup actions
    #[serde(skip_serializing_if = "Option::is_none", rename = "groupID")]
    pub group_id: Option<String>,
    /// optional recipient override for direct p2p
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recipient: Option<String>,
}

impl MixnetEnvelope {
    /// Create a query message for a given username
    pub fn query(usernym: &str) -> Self {
        Self {
            action: "query".into(),
            username: Some(usernym.into()),
            usernym: None,
            public_key: None,
            field: None,
            value: None,
            content: None,
            context: None,
            signature: None,
            target: None,
            group_id: None,
            recipient: None,
        }
    }

    /// Register a new user with public key
    pub fn register(usernym: &str, public_key: &str) -> Self {
        Self {
            action: "register".into(),
            username: None,
            usernym: Some(usernym.into()),
            public_key: Some(public_key.into()),
            field: None,
            value: None,
            content: None,
            context: None,
            signature: None,
            target: None,
            group_id: None,
            recipient: None,
        }
    }

    /// Login an existing usernym
    pub fn login(usernym: &str) -> Self {
        Self {
            action: "login".into(),
            username: None,
            usernym: Some(usernym.into()),
            public_key: None,
            field: None,
            value: None,
            content: None,
            context: None,
            signature: None,
            target: None,
            group_id: None,
            recipient: None,
        }
    }

    /// Update a field to a new value with signature
    pub fn update(field: &str, value: &str, signature: &str) -> Self {
        Self {
            action: "update".into(),
            username: None,
            usernym: None,
            public_key: None,
            field: Some(field.into()),
            value: Some(value.into()),
            content: None,
            context: None,
            signature: Some(signature.into()),
            target: None,
            group_id: None,
            recipient: None,
        }
    }

    /// Send a message via the central mixnet server
    pub fn send(content: &str, signature: &str) -> Self {
        Self {
            action: "send".into(),
            username: None,
            usernym: None,
            public_key: None,
            field: None,
            value: None,
            content: Some(content.into()),
            context: None,
            signature: Some(signature.into()),
            target: None,
            group_id: None,
            recipient: None,
        }
    }

    /// Create a direct p2p message envelope
    pub fn direct_message(content: &str, signature: &str) -> Self {
        Self {
            action: "incomingMessage".into(),
            username: None,
            usernym: None,
            public_key: None,
            field: None,
            value: None,
            content: Some(content.into()),
            context: Some("chat".into()),
            signature: Some(signature.into()),
            target: None,
            group_id: None,
            recipient: None,
        }
    }

    /// Send a message to a group
    pub fn send_group(target: &str, content: &str, signature: &str) -> Self {
        Self {
            action: "sendGroup".into(),
            username: None,
            usernym: None,
            public_key: None,
            field: None,
            value: None,
            content: Some(content.into()),
            context: None,
            signature: Some(signature.into()),
            target: Some(target.into()),
            group_id: None,
            recipient: None,
        }
    }

    /// Create a new group
    pub fn create_group(signature: &str) -> Self {
        Self {
            action: "createGroup".into(),
            username: None,
            usernym: None,
            public_key: None,
            field: None,
            value: None,
            content: None,
            context: None,
            signature: Some(signature.into()),
            target: None,
            group_id: None,
            recipient: None,
        }
    }

    /// Invite a user to a group
    pub fn invite_group(target: &str, group_id: &str, signature: &str) -> Self {
        Self {
            action: "inviteGroup".into(),
            username: None,
            usernym: None,
            public_key: None,
            field: None,
            value: None,
            content: None,
            context: None,
            signature: Some(signature.into()),
            target: Some(target.into()),
            group_id: Some(group_id.into()),
            recipient: None,
        }
    }

    /// Registration response from server
    pub fn registration_response(username: &str, signature: &str) -> Self {
        Self {
            action: "registrationResponse".into(),
            username: Some(username.into()),
            usernym: None,
            public_key: None,
            field: None,
            value: None,
            content: None,
            context: None,
            signature: Some(signature.into()),
            target: None,
            group_id: None,
            recipient: None,
        }
    }

    /// Login response from server
    pub fn login_response(username: &str, signature: &str) -> Self {
        Self {
            action: "loginResponse".into(),
            username: Some(username.into()),
            usernym: None,
            public_key: None,
            field: None,
            value: None,
            content: None,
            context: None,
            signature: Some(signature.into()),
            target: None,
            group_id: None,
            recipient: None,
        }
    }

    /// Serialize to JSON string
    pub fn to_json(&self) -> Result<String> {
        Ok(serde_json::to_string(self)?)
    }
}
