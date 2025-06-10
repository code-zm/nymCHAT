use anyhow::Result;
use sqlx::{Row, SqlitePool};
use std::path::Path;

#[derive(Clone)]
pub struct DbUtils {
    pool: SqlitePool,
}

impl DbUtils {
    /// Open or create the SQLite database at the specified path.
    pub async fn new<P: AsRef<Path>>(db_path: P) -> Result<Self> {
        let db_url = format!("sqlite://{}", db_path.as_ref().display());
        let pool = SqlitePool::connect(&db_url).await?;
        sqlx::query(
            r#"
            PRAGMA journal_mode = WAL;
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS users (
                username   TEXT PRIMARY KEY,
                publicKey  TEXT NOT NULL,
                senderTag  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS groups (
                groupID    TEXT PRIMARY KEY,
                userList   TEXT NOT NULL
            );
            "#,
        )
        .execute(&pool)
        .await?;
        Ok(DbUtils { pool })
    }

    /// Retrieve a user by username. Returns (username, publicKey, senderTag).
    pub async fn get_user_by_username(
        &self,
        username: &str,
    ) -> Result<Option<(String, String, String)>> {
        let row = sqlx::query(
            "SELECT username, publicKey, senderTag FROM users WHERE username = ?",
        )
        .bind(username)
        .fetch_optional(&self.pool)
        .await?;
        Ok(row.map(|r| (r.get(0), r.get(1), r.get(2))))
    }

    /// Add a new user. Returns true on success.
    pub async fn add_user(
        &self,
        username: &str,
        public_key: &str,
        sender_tag: &str,
    ) -> Result<bool> {
        let res = sqlx::query(
            "INSERT INTO users (username, publicKey, senderTag) VALUES (?, ?, ?)",
        )
        .bind(username)
        .bind(public_key)
        .bind(sender_tag)
        .execute(&self.pool)
        .await?;
        Ok(res.rows_affected() > 0)
    }

    /// Update a single field of a user. Returns true on success.
    pub async fn update_user_field(
        &self,
        username: &str,
        field: &str,
        value: &str,
    ) -> Result<bool> {
        let sql = format!("UPDATE users SET {} = ? WHERE username = ?", field);
        let res = sqlx::query(&sql)
            .bind(value)
            .bind(username)
            .execute(&self.pool)
            .await?;
        Ok(res.rows_affected() > 0)
    }
}