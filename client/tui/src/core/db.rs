//! In-memory stub persistence for users, contacts, and messages
#![allow(dead_code)]
use anyhow::Result;
use chrono::{DateTime, Utc};
use std::collections::HashMap;
use std::sync::Mutex;

/// Simple in-memory database stub
pub struct Db {
    users: Mutex<HashMap<String, String>>,
}

impl Db {
    /// Open or create a database (stub ignores path)
    pub fn open(_path: &str) -> Result<Self> {
        Ok(Db {
            users: Mutex::new(HashMap::new()),
        })
    }

    /// Initialize global tables (no-op)
    pub fn init_global(&self) -> Result<()> {
        Ok(())
    }

    /// Initialize user-specific tables (no-op)
    pub fn init_user(&self, _username: &str) -> Result<()> {
        Ok(())
    }

    /// Register a new user with public key
    pub fn register_user(&self, username: &str, public_key: &str) -> Result<()> {
        let mut u = self.users.lock().unwrap();
        u.insert(username.to_string(), public_key.to_string());
        Ok(())
    }

    /// Add a contact (no-op)
    pub fn add_contact(&self, _me: &str, _user: &str, _public_key: &str) -> Result<()> {
        Ok(())
    }

    /// Get a contact's public key (stub returns None)
    pub fn get_contact(&self, _me: &str, _user: &str) -> Result<Option<(String, String)>> {
        Ok(None)
    }

    /// Get a registered user's public key
    pub fn get_user(&self, username: &str) -> Result<Option<(String, String)>> {
        let u = self.users.lock().unwrap();
        if let Some(pk) = u.get(username) {
            Ok(Some((username.to_string(), pk.clone())))
        } else {
            Ok(None)
        }
    }

    /// Save a message (no-op)
    pub fn save_message(
        &self,
        _me: &str,
        _contact: &str,
        _sent: bool,
        _text: &str,
        _ts: DateTime<Utc>,
    ) -> Result<()> {
        Ok(())
    }

    /// Load contacts (stub empty)
    pub fn load_contacts(&self, _me: &str) -> Result<Vec<(String, String)>> {
        Ok(Vec::new())
    }

    /// Load messages (stub empty)
    pub fn load_messages(
        &self,
        _me: &str,
        _contact: &str,
    ) -> Result<Vec<(bool, String, chrono::DateTime<chrono::Utc>)>> {
        Ok(Vec::new())
    }
}
