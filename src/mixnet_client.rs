use futures::StreamExt;
use nym_sdk::mixnet::{MixnetClient, MixnetClientSender, MixnetMessageSender, Recipient};
use std::sync::Arc;
use tokio::sync::{Mutex, Notify}; // ✅ Import Notify for shutdown signaling
use pyo3::prelude::*; // Needed for PyObject

pub struct MixnetHandler {
    client: Arc<Mutex<Option<MixnetClient>>>,
    sender: MixnetClientSender,
    message_callback: Arc<Mutex<Option<PyObject>>>,
    listening: Arc<Mutex<bool>>, // Track if the listener is running
    shutdown_signal: Arc<Notify>, // ✅ Shutdown signal for stopping the listener
}

impl MixnetHandler {
    /// Creates a new Mixnet client.
    pub async fn new() -> anyhow::Result<Self> {
        let client = MixnetClient::connect_new().await?;
        let sender = client.split_sender();
        Ok(Self {
            client: Arc::new(Mutex::new(Some(client))),
            sender,
            message_callback: Arc::new(Mutex::new(None)),
            listening: Arc::new(Mutex::new(false)), // Initialize listener state
            shutdown_signal: Arc::new(Notify::new()), // ✅ Initialize shutdown signal
        })
    }

    /// Sets a Python callback for handling incoming messages.
    pub async fn set_callback(&self, callback: PyObject) {
        let mut cb = self.message_callback.lock().await;
        *cb = Some(callback);
    }

    /// Retrieves the client's Nym address.
    pub async fn get_nym_address(&self) -> Option<String> {
        let lock = self.client.lock().await;
        lock.as_ref().map(|c| c.nym_address().to_string())
    }

    /// Sends a message through the Mixnet.
    pub async fn send_message(&self, recipient: &str, message: &str) -> anyhow::Result<()> {
        let parsed_recipient = recipient.parse::<Recipient>()?;
        println!("🚀 Sending message to: {}", recipient);
        self.sender.send_plain_message(parsed_recipient, message).await?;
        println!("✅ Message sent successfully!");
        Ok(())
    }

    /// Start listening for incoming messages (only if not already running).
    pub async fn receive_messages(&self) {
        let mut listening = self.listening.lock().await;
        if *listening {
            println!("⚠️ Listener already running, skipping...");
            return;
        }
        *listening = true;
        drop(listening); // Release the lock before spawning

        let client_ref = Arc::clone(&self.client);
        let callback_ref = Arc::clone(&self.message_callback);
        let shutdown_signal = Arc::clone(&self.shutdown_signal); // ✅ Clone shutdown signal

        tokio::spawn(async move {
            let mut lock = client_ref.lock().await;
            if let Some(client) = lock.as_mut() {
                println!("📡 Listening for incoming messages...");
                loop {
                    tokio::select! {
                        _ = shutdown_signal.notified() => { // ✅ Stop when shutdown is triggered
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

    /// Disconnects the Mixnet client.
    pub async fn disconnect(&self) {
        println!("🚪 Stopping background tasks...");
        self.shutdown_signal.notify_waiters(); // ✅ Signal the listener to stop

        let mut lock = self.client.lock().await;
        if let Some(client) = lock.take() {
            println!("🔌 Disconnecting Mixnet client...");
            client.disconnect().await;
            println!("✅ Client disconnected.");
        }
    }
}

