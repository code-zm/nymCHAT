mod crypto_utils;
mod db_utils;
mod env_loader;
mod log_config;
mod message_utils;

use crate::crypto_utils::CryptoUtils;
use crate::db_utils::DbUtils;
use crate::env_loader::load_env;
use crate::log_config::init_logging;
use crate::message_utils::MessageUtils;
use tokio_stream::StreamExt;
use nym_sdk::mixnet::{MixnetClientBuilder, MixnetClientSender, StoragePaths};
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::Mutex;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Load environment and configure logging
    load_env();
    let log_file = std::env::var("LOG_FILE_PATH")?;
    init_logging(&log_file)?;

    // Ensure storage directories exist
    let db_path = std::env::var("DATABASE_PATH")?;
    if let Some(parent) = PathBuf::from(&db_path).parent() {
        std::fs::create_dir_all(parent)?;
    }
    let keys_dir = std::env::var("KEYS_DIR")?;
    std::fs::create_dir_all(&keys_dir)?;

    // Load encryption password
    let secret_path = std::env::var("SECRET_PATH")?;
    let password = std::fs::read_to_string(&secret_path)?.trim().to_string();

    // Initialize utilities
    let crypto = CryptoUtils::new(PathBuf::from(&keys_dir), password.clone())?;
    let db = DbUtils::new(&db_path).await?;

    // Initialize mixnet client storage path
    let client_id = std::env::var("NYM_CLIENT_ID")?;
    let storage_dir =
        std::env::var("NYM_SDK_STORAGE").unwrap_or_else(|_| format!("storage/{}", client_id));
    let storage_paths = StoragePaths::new_from_dir(PathBuf::from(storage_dir))?;

    // Build and connect the mixnet client
    let builder = MixnetClientBuilder::new_with_default_storage(storage_paths).await?;
    let client_inner = builder.build()?.connect_to_mixnet().await?;
    let sender = client_inner.split_sender();
    let address = client_inner.nym_address();
    log::info!("Connected to mixnet. Nym Address: {}", address);

    // Shared client for message handler (wrapped in Option to allow graceful shutdown)
    let client = Arc::new(Mutex::new(Some(client_inner)));
    let mut message_utils = MessageUtils::new(client_id.clone(), sender, db, crypto);

    // Spawn message receiving task
    {
        let client_ref = client.clone();
        tokio::spawn(async move {
            let mut guard = client_ref.lock().await;
            if let Some(client) = guard.as_mut() {
                while let Some(msg) = client.next().await {
                    message_utils.process_received_message(msg).await;
                }
            }
        });
    }

    // Wait for CTRL+C and shutdown
    tokio::signal::ctrl_c().await?;
    log::info!("Shutting down mixnet client.");
    if let Some(client) = client.lock().await.take() {
        client.disconnect().await;
    }
    Ok(())
}
