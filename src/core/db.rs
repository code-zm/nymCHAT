//! SQLite persistence using the schema from dbUtils.py
use anyhow::Result;
use chrono::{DateTime, Utc};
use sqlx::{Row, SqlitePool, sqlite::SqlitePoolOptions};
use std::{fs, path::Path};

/// SQLite-backed database.
pub struct Db {
    pool: SqlitePool,
}

impl Db {
    /// Open or create a database at the given path.
    pub async fn open(path: &str) -> Result<Self> {
        // ensure parent directories exist so SQLite can create/open the file
        if let Some(dir) = Path::new(path).parent() {
            fs::create_dir_all(dir)?;
        }
        let url = format!("sqlite://{}?mode=rwc", path);
        let pool = SqlitePoolOptions::new().max_connections(5).connect(&url).await?;
        Ok(Db { pool })
    }

    /// Create global tables (users).
    pub async fn init_global(&self) -> Result<()> {
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                public_key TEXT NOT NULL
            )
            "#,
        )
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    /// Create per-user tables (contacts and messages).
    pub async fn init_user(&self, username: &str) -> Result<()> {
        let contacts_table = format!("contacts_{}", username);
        let messages_table = format!("messages_{}", username);
        sqlx::query(&format!(
            r#"
            CREATE TABLE IF NOT EXISTS {contacts_table} (
                username TEXT PRIMARY KEY,
                public_key TEXT NOT NULL
            )
            "#,
            contacts_table = contacts_table,
        ))
        .execute(&self.pool)
        .await?;
        sqlx::query(&format!(
            r#"
            CREATE TABLE IF NOT EXISTS {messages_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                type TEXT CHECK(type IN ('to','from')) NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            "#,
            messages_table = messages_table,
        ))
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    /// Register a new user and create their tables.
    pub async fn register_user(&self, username: &str, public_key: &str) -> Result<()> {
        sqlx::query(
            r#"INSERT OR REPLACE INTO users (username, public_key) VALUES (?, ?)"#,
        )
        .bind(username)
        .bind(public_key)
        .execute(&self.pool)
        .await?;
        self.init_user(username).await?;
        Ok(())
    }

    /// Add or update a contact for the given user.
    pub async fn add_contact(
        &self,
        me: &str,
        user: &str,
        public_key: &str,
    ) -> Result<()> {
        let table = format!("contacts_{}", me);
        sqlx::query(&format!(
            r#"INSERT OR REPLACE INTO {table} (username, public_key) VALUES (?, ?)"#,
            table = table
        ))
        .bind(user)
        .bind(public_key)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    /// Get a contact's public key for the given user.
    pub async fn get_contact(
        &self,
        me: &str,
        user: &str,
    ) -> Result<Option<(String, String)>> {
        let table = format!("contacts_{}", me);
        if let Some(row) = sqlx::query(&format!(
            r#"SELECT username, public_key FROM {table} WHERE username = ?"#,
            table = table
        ))
        .bind(user)
        .fetch_optional(&self.pool)
        .await? {
            let name: String = row.try_get("username")?;
            let pk: String = row.try_get("public_key")?;
            Ok(Some((name, pk)))
        } else {
            Ok(None)
        }
    }

    /// Get a registered user's public key.
    pub async fn get_user(&self, username: &str) -> Result<Option<(String, String)>> {
        let row = sqlx::query(
            r#"SELECT username, public_key FROM users WHERE username = ?"#,
        )
        .bind(username)
        .fetch_optional(&self.pool)
        .await?;
        if let Some(r) = row {
            let name: String = r.try_get("username")?;
            let pk: String = r.try_get("public_key")?;
            Ok(Some((name, pk)))
        } else {
            Ok(None)
        }
    }

    /// Save a message (to/from) for the given user.
    pub async fn save_message(
        &self,
        me: &str,
        contact: &str,
        sent: bool,
        text: &str,
        ts: DateTime<Utc>,
    ) -> Result<()> {
        let table = format!("messages_{}", me);
        let msg_type = if sent { "to" } else { "from" };
        sqlx::query(&format!(
            r#"
            INSERT INTO {table} (username, type, message, timestamp)
            VALUES (?, ?, ?, ?)
            "#,
            table = table
        ))
        .bind(contact)
        .bind(msg_type)
        .bind(text)
        .bind(ts)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    /// Load all contacts for the given user.
    pub async fn load_contacts(&self, me: &str) -> Result<Vec<(String, String)>> {
        let table = format!("contacts_{}", me);
        let rows = sqlx::query(&format!(
            r#"SELECT username, public_key FROM {table}"#,
            table = table
        ))
        .fetch_all(&self.pool)
        .await?;
        Ok(rows
            .into_iter()
            .map(|r| {
                let name: String = r.try_get("username").unwrap();
                let pk: String = r.try_get("public_key").unwrap();
                (name, pk)
            })
            .collect())
    }

    /// Load all messages exchanged with a contact for the given user.
    pub async fn load_messages(
        &self,
        me: &str,
        contact: &str,
    ) -> Result<Vec<(bool, String, DateTime<Utc>)>> {
        let table = format!("messages_{}", me);
        let rows = sqlx::query(&format!(
            r#"
            SELECT type, message, timestamp
            FROM {table}
            WHERE username = ?
            ORDER BY timestamp ASC
            "#,
            table = table
        ))
        .bind(contact)
        .fetch_all(&self.pool)
        .await?;
        let mut msgs = Vec::new();
        for row in rows {
            let t: String = row.try_get("type")?;
            let sent = t == "to";
            let msg: String = row.try_get("message")?;
            let ts: DateTime<Utc> = row.try_get("timestamp")?;
            msgs.push((sent, msg, ts));
        }
        Ok(msgs)
    }
}
