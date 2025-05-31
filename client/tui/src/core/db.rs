//! In-memory stub persistence for users, contacts, and messages
//! SQLite-backed persistence for users, contacts, and messages
#![allow(dead_code)]
use anyhow::Result;
use chrono::{DateTime, Utc};
use sqlx::{Row, SqlitePool};
use std::path::Path;

/// Simple in-memory database stub
/// SQLite persistence
#[derive(Clone)]
pub struct Db {
    pool: SqlitePool,
}

impl Db {
    /// Open or create the sqlite database at `path` (e.g. "/data/app.db")
    pub async fn open<P: AsRef<Path>>(path: P) -> Result<Self> {
        let db_url = format!("sqlite://{}", path.as_ref().display());
        let pool = SqlitePool::connect(&db_url).await?;
        // Enable WAL and foreign keys, create tables
        sqlx::query(r#"
            PRAGMA journal_mode = WAL;
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS users (
              username   TEXT PRIMARY KEY,
              public_key TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS contacts (
              owner      TEXT NOT NULL,
              contact    TEXT NOT NULL,
              public_key TEXT NOT NULL,
              PRIMARY KEY(owner, contact),
              FOREIGN KEY(owner) REFERENCES users(username)
            );
            CREATE TABLE IF NOT EXISTS messages (
              owner   TEXT NOT NULL,
              contact TEXT NOT NULL,
              sent    INTEGER NOT NULL,
              text    TEXT NOT NULL,
              ts      TEXT NOT NULL
            );
        "#)
        .execute(&pool)
        .await?;
        Ok(Db { pool })
    }

    /// Initialize global tables (no-op)
    /// No additional init needed
    pub fn init_global(&self) -> Result<()> {
        Ok(())
    }

    /// Initialize user-specific tables (no-op)
    /// No per-user schema
    pub fn init_user(&self, _username: &str) -> Result<()> {
        Ok(())
    }

    /// Register a new user with public key
    /// Insert or update a user's public key
    pub async fn register_user(&self, username: &str, public_key: &str) -> Result<()> {
        sqlx::query("INSERT OR REPLACE INTO users (username, public_key) VALUES (?, ?)")
            .bind(username)
            .bind(public_key)
            .execute(&self.pool)
            .await?;
        Ok(())
    }

    /// Add a contact (no-op)
    /// Add or update a contact
    pub async fn add_contact(&self, me: &str, user: &str, public_key: &str) -> Result<()> {
        sqlx::query("INSERT OR REPLACE INTO contacts (owner, contact, public_key) VALUES (?, ?, ?)")
            .bind(me)
            .bind(user)
            .bind(public_key)
            .execute(&self.pool)
            .await?;
        Ok(())
    }

    /// Get a contact's public key (stub returns None)
    /// Lookup a contact
    pub async fn get_contact(&self, me: &str, user: &str) -> Result<Option<(String, String)>> {
        let row = sqlx::query(
            "SELECT contact, public_key FROM contacts WHERE owner = ? AND contact = ?",
        )
        .bind(me)
        .bind(user)
        .fetch_optional(&self.pool)
        .await?;
        Ok(row.map(|r| (r.get(0), r.get(1))))
    }

    /// Get a registered user's public key
    /// Lookup a user
    pub async fn get_user(&self, username: &str) -> Result<Option<(String, String)>> {
        let row = sqlx::query(
            "SELECT username, public_key FROM users WHERE username = ?",
        )
        .bind(username)
        .fetch_optional(&self.pool)
        .await?;
        Ok(row.map(|r| (r.get(0), r.get(1))))
    }

    /// Save a message (no-op)
    /// Persist a chat message
    pub async fn save_message(
        &self,
        me: &str,
        contact: &str,
        sent: bool,
        text: &str,
        ts: DateTime<Utc>,
    ) -> Result<()> {
        sqlx::query(
            "INSERT INTO messages (owner, contact, sent, text, ts) VALUES (?, ?, ?, ?, ?)",
        )
        .bind(me)
        .bind(contact)
        .bind(sent as i32)
        .bind(text)
        .bind(ts.to_rfc3339())
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    /// Load contacts (stub empty)
    /// Load all contacts for a user
    pub async fn load_contacts(&self, me: &str) -> Result<Vec<(String, String)>> {
        let rows = sqlx::query(
            "SELECT contact, public_key FROM contacts WHERE owner = ?",
        )
        .bind(me)
        .fetch_all(&self.pool)
        .await?;
        Ok(rows.into_iter().map(|r| (r.get(0), r.get(1))).collect())
    }

    /// Load messages (stub empty)
    /// Load all messages between a user and contact
    pub async fn load_messages(
        &self,
        me: &str,
        contact: &str,
    ) -> Result<Vec<(bool, String, DateTime<Utc>)>> {
        let rows = sqlx::query(
            "SELECT sent, text, ts FROM messages WHERE owner = ? AND contact = ? ORDER BY ts",
        )
        .bind(me)
        .bind(contact)
        .fetch_all(&self.pool)
        .await?;
        let mut out = Vec::with_capacity(rows.len());
        for row in rows {
            let sent: i32 = row.get(0);
            let text: String = row.get(1);
            let ts_s: String = row.get(2);
            let ts = DateTime::parse_from_rfc3339(&ts_s)?.with_timezone(&Utc);
            out.push((sent != 0, text, ts));
        }
        Ok(out)
    }
}
