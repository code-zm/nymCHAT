#!/bin/bash
set -e

# Function to log messages
log() {
    local level="$1"
    local message="$2"
    echo "[$level] $message"
}

# Function to install Rust if it's not already installed
install_rust() {
    if ! command -v rustc >/dev/null 2>&1; then
        log "INFO" "Rust not found. Installing Rust toolchain..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        # Source the environment to update PATH with Cargo binaries
        source "$HOME/.cargo/env"
        log "INFO" "Rust installed successfully!"
    else
        log "INFO" "Rust is already installed: $(rustc --version)"
    fi
}

# Install Rust toolchain if necessary
install_rust

# Install Python dependencies
log "INFO" "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

# Build the Rust extension using maturin
log "INFO" "Building Rust extension..."
cd async_ffi
maturin build

# Install the built wheel
log "INFO" "Installing the built wheel..."
pip install --no-cache-dir target/wheels/*.whl
