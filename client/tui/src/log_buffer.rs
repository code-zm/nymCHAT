//! Global log buffer for capturing mixnet client logs
use once_cell::sync::Lazy;
use std::sync::Mutex;

/// Stores recent log lines for display in the TUI
pub static LOG_BUFFER: Lazy<Mutex<Vec<String>>> = Lazy::new(|| Mutex::new(Vec::new()));
