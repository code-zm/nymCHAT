#!/bin/bash
set -e

# Function to log messages
log() {
    echo "[$1] $2"
}

# Install Rust if it's not already available
if ! command -v rustc >/dev/null 2>&1; then
    log "INFO" "Rust not found. Installing Rust toolchain..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
    log "INFO" "Rust installed successfully!"
else
    log "INFO" "Rust is already installed: $(rustc --version)"
fi

log "INFO" "Installing maturin"
pip install --no-cache-dir maturin
# Build the Rust extension using maturin
log "INFO" "Building Rust extension..."
cd async_ffi
maturin build --release
