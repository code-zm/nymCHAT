#!/bin/bash
set -e

# Define URLs and directories
NYM_BINARY_URL="https://github.com/nymtech/nym/releases/download/nym-binaries-v2025.4-dorina-patched/nym-client"
CLIENT_ID=${NYM_CLIENT_ID:-"nymserver"}
ENV_FILE="/app/.env"
ENV_EXAMPLE="/app/.env.example"
PASSWORD_FILE="/app/secrets/encryption_password"
HOST_PASSWORD_FILE="/app/password.txt"  # Expected before copying
STORAGE_DIR="/app/storage"
NYM_CONFIG_DIR="/root/.nym"
BUILD_DIR="/tmp/nym-build"
INSTALL_DIR="/app"

# Logging function
log() {
    local level="$1"
    local message="$2"
    local color_start=""
    local color_end=""

    if [[ -t 1 ]]; then
        case "$level" in
            "INFO")  color_start="\033[0;32m" ;;  # Green
            "WARN")  color_start="\033[0;33m" ;;  # Yellow
            "ERROR") color_start="\033[0;31m" ;;  # Red
            "DEBUG") color_start="\033[0;36m" ;;  # Cyan
        esac
        color_end="\033[0m"
    fi

    echo -e "${color_start}[$level] $message${color_end}"
}

# Detect OS and architecture
detect_os() {
    case "$(uname -s)" in
        Linux*)     OS="linux";;
        Darwin*)    OS="macos";;
        CYGWIN*|MINGW*|MSYS*) OS="windows";;
        *)          OS="unknown";;
    esac

    case "$(uname -m)" in
        x86_64)     ARCH="x86_64";;
        i386|i686)  ARCH="x86";;
        arm64|aarch64) ARCH="aarch64";;
        armv7*)     ARCH="arm";;
        *)          ARCH="unknown";;
    esac

    log "INFO" "Detected system: $OS ($ARCH)"
}

# Install system dependencies
install_dependencies() {
    log "INFO" "[PHASE] Installing required system packages..."

    apt-get update

    # Install only the absolutely necessary dependencies for Rust and Nym
    apt-get install -y \
        git \
        cmake \
        pkg-config \
        libssl-dev

    log "INFO" "System dependencies installed successfully!"
}

# Install the Nym client binary in /app/
install_binary() {
    log "INFO" "[PHASE] Installing Nym client binary..."
    INSTALL_PATH="$INSTALL_DIR/nym-client"

    if [ -f "$INSTALL_PATH" ]; then
        log "INFO" "Using existing binary"
        return
    fi

    log "INFO" "Downloading Nym client from $NYM_BINARY_URL"
    curl -L "$NYM_BINARY_URL" -o "$INSTALL_PATH"
    chmod +x "$INSTALL_PATH"
    log "INFO" "Nym client installed in /app/"
}

# Ensure storage directories exist and have correct permissions
setup_storage() {
    log "INFO" "[PHASE] Setting up storage directories..."
    
    mkdir -p "$STORAGE_DIR"
    chmod -R 777 "$STORAGE_DIR"  # Ensure all users can write logs

    mkdir -p /app/secrets
    chmod -R 700 /app/secrets  # Only allow root to read secrets

    mkdir -p "$NYM_CONFIG_DIR"
    chmod -R 700 "$NYM_CONFIG_DIR"

    log "INFO" "Storage directories are set up."
}

# Copy encryption password
setup_encryption_password() {
    log "INFO" "[PHASE] Setting up encryption password..."
    
    if [ ! -f "/app/secrets/encryption_password" ]; then
        if [ -f "/app/password.txt" ]; then
            log "INFO" "Copying encryption password into /app/secrets/"
            mkdir -p /app/secrets
            cp "/app/password.txt" "/app/secrets/encryption_password"
        else
            log "WARN" "No password.txt found! Generating a random encryption password."
            mkdir -p /app/secrets
            openssl rand -base64 32 > "/app/secrets/encryption_password"
        fi
        chmod 600 "/app/secrets/encryption_password"
        log "INFO" "Encryption password successfully set up in /app/secrets/"
    else
        log "INFO" "Encryption password already exists in /app/secrets/. Skipping setup."
    fi
}

# Generate .env file from .env.example
generate_env_file() {
    log "INFO" "[PHASE] Generating .env file..."
    
    if [ ! -f "$ENV_EXAMPLE" ]; then
        log "ERROR" ".env.example not found in /app!"
        exit 1
    fi

    # Replace placeholders and create .env
    sed "s/{NYM_CLIENT_ID}/$CLIENT_ID/g" "$ENV_EXAMPLE" > "$ENV_FILE"

    chmod 600 "$ENV_FILE"  # Restrict access for security
    log "INFO" ".env file created at $ENV_FILE"
}

# Install Rust if needed
install_rust() {
    if ! command -v rustc >/dev/null 2>&1; then
        log "INFO" "Rust not found. Installing Rust toolchain..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
        log "INFO" "Rust installed successfully!"
    else
        log "INFO" "Rust is already installed: $(rustc --version)"
    fi
}

# Build nym-client from source
build_nym_client() {
    log "INFO" "Cloning Nym repository from GitHub..."
    rm -rf "$BUILD_DIR"
    git clone --depth 1 "https://github.com/nymtech/nym.git" "$BUILD_DIR"
    
    cd "$BUILD_DIR"
    
    log "INFO" "Building `nym-client` for architecture: $ARCH..."
    cargo build --release --bin nym-client
    
    if [[ -f "target/release/nym-client" ]]; then
        log "INFO" "Build successful! Moving binary to installation directory..."
        mv "target/release/nym-client" "$INSTALL_DIR/nym-client"
        chmod +x "$INSTALL_DIR/nym-client"
        log "INFO" "nym-client installed at $INSTALL_DIR/nym-client"
    else
        log "ERROR" "Build failed! Check logs for details."
        exit 1
    fi

    # Clean up build files to save space
    log "INFO" "Cleaning up build directory..."
    rm -rf "$BUILD_DIR"
}

# Main execution flow
log "INFO" "============================================================="
log "INFO" "NYM CLIENT INSTALLATION AND CONFIGURATION"
log "INFO" "Client ID: $CLIENT_ID"
log "INFO" "============================================================="

detect_os
install_dependencies
setup_storage
setup_encryption_password
generate_env_file

# Determine whether to use prebuilt binary or build from source
if [[ "$ARCH" != "x86_64" && "$ARCH" != "x86" ]]; then
    log "INFO" "Forcing build from source due to architecture: $ARCH"
    install_rust
    build_nym_client
else
    log "INFO" "Using prebuilt binary for Linux ($ARCH)"
    install_binary
fi

log "INFO" "[COMPLETE] Nym client installation successful"
