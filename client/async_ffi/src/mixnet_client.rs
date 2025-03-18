use futures::StreamExt;
use nym_sdk::mixnet::{MixnetClient, MixnetClientSender, MixnetMessageSender, Recipient};
use std::sync::Arc;
use tokio::sync::{Mutex, Notify};
use pyo3::prelude::*;
use anyhow::Context;

pub struct MixnetHandler {
    client: Arc<Mutex<Option<MixnetClient>>>,
    sender: MixnetClientSender,
    message_callback: Arc<Mutex<Option<PyObject>>>,
    listening: Arc<Mutex<bool>>,
    shutdown_signal: Arc<Notify>,
}

impl MixnetHandler {
    /// Creates a new Mixnet client.
    pub async fn new() -> anyhow::Result<Self> {
        let client = nym_sdk::mixnet::MixnetClientBuilder::new_ephemeral()
            .build()
            .context("Failed to build ephemeral client")?
            .connect_to_mixnet()
            .await
            .context("Failed to connect to mixnet")?;

        let sender = client.split_sender();
        Ok(Self {
            client: Arc::new(Mutex::new(Some(client))),
            sender,
            message_callback: Arc::new(Mutex::new(None)),
            listening: Arc::new(Mutex::new(false)),
            shutdown_signal: Arc::new(Notify::new()),
        })
    }

    pub async fn set_callback(&self, callback: PyObject) {
        let mut cb = self.message_callback.lock().await;
        *cb = Some(callback);
    }

    pub async fn get_nym_address(&self) -> Option<String> {
        let lock = self.client.lock().await;
        lock.as_ref().map(|c| c.nym_address().to_string())
    }

    pub async fn send_message(&self, recipient: &str, message: &str) -> anyhow::Result<()> {
    let parsed_recipient = recipient
        .parse::<Recipient>()
        .context("Failed to parse recipient address")?;

    println!("🚀 Sending message to: {}", recipient);

    self.sender
        .send_message(
            parsed_recipient,
            message.as_bytes().to_vec(),
            nym_sdk::mixnet::IncludedSurbs::Amount(10), // 👈 Corrected here
        )
        .await
        .context("Failed to send message with SURBs")?;

    println!("✅ Message sent successfully with 10 SURBs included!");
    Ok(())
}



    pub async fn receive_messages(&self) {
        let mut listening = self.listening.lock().await;
        if *listening {
            println!("⚠️ Listener already running, skipping...");
            return;
        }
        *listening = true;
        drop(listening);

        let client_ref = Arc::clone(&self.client);
        let callback_ref = Arc::clone(&self.message_callback);
        let shutdown_signal = Arc::clone(&self.shutdown_signal);

        tokio::spawn(async move {
            let mut lock = client_ref.lock().await;
            if let Some(client) = lock.as_mut() {
                println!("📡 Listening for incoming messages...");
                loop {
                    tokio::select! {
                        _ = shutdown_signal.notified() => {
                            println!("🛑 Listener stopping...");
                            break;
                        }
                        received = client.next() => {
                            if let Some(received) = received {
                                if !received.message.is_empty() {
                                    let msg_str = String::from_utf8_lossy(&received.message).to_string();
                                    let callback = callback_ref.lock().await;
                                    pyo3::Python::with_gil(|py| {
                                        if let Some(ref callback) = *callback {
                                            if let Err(e) = callback.call1(py, (&msg_str,)) {
                                                e.print(py);
                                            }
                                        } else {
                                            println!("📩 Received: {}", msg_str);
                                        }
                                    });
                                }
                            }
                        }
                    }
                }
            }
        });
    }

    pub async fn disconnect(&self) {
        println!("🚪 Stopping background tasks...");
        self.shutdown_signal.notify_waiters();

        let mut lock = self.client.lock().await;
        if let Some(client) = lock.take() {
            println!("🔌 Disconnecting Mixnet client...");
            client.disconnect().await;
            println!("✅ Client disconnected.");
        }
    }
}

