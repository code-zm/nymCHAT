#!/bin/bash
set -e

# Define URLs and directories
ENV_EXAMPLE="/app/.env.example"
PASSWORD_FILE="/app/secrets/encryption_password"
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

    apt-get update  # Always update package lists first

    if [[ "$ARCH" == "x86_64" || "$ARCH" == "x86" ]]; then
        log "INFO" "Detected $ARCH, installing only curl (prebuilt binary will be used)"
        apt-get install -y curl
    else
        log "INFO" "Detected $ARCH, installing full build dependencies for Rust"
        apt-get install -y git build-essential cmake pkg-config libssl-dev curl
    fi

    log "INFO" "System dependencies installed successfully!"
}


# Fetch the latest version of from nymtech/nym repo
fetch_latest_version() {
    log "INFO" "Fetching latest Nym release version from GitHub..."
    LATEST_VERSION=$(curl -fsSL "https://api.github.com/repos/nymtech/nym/releases/latest" | grep '"tag_name":' | cut -d '"' -f 4)

    if [[ -z "$LATEST_VERSION" ]]; then
        log "ERROR" "Failed to fetch latest version. Exiting."
        exit 1
    fi

    NYM_BINARY_URL="https://github.com/nymtech/nym/releases/download/${LATEST_VERSION}/nym-client"
    HASH_URL="https://github.com/nymtech/nym/releases/download/${LATEST_VERSION}/hashes.json"

    log "INFO" "Latest Nym version: $LATEST_VERSION"
}

# Install the Nym client binary in /app/
install_binary() {
    log "INFO" "[PHASE] Installing Nym client binary..."
    local install_path="$INSTALL_DIR/nym-client"

    mkdir -p "$INSTALL_DIR"

    log "INFO" "Downloading Nym client from $NYM_BINARY_URL"
    curl -L "$NYM_BINARY_URL" -o "$install_path"
    chmod +x "$install_path"

    # Verify the binary
    verify_binary "$install_path"
}

# Ensure our download hash matches Nym's
verify_binary() {
    local binary="$1"
    local hash_file="/tmp/hashes.json"

    log "INFO" "Fetching latest hash file from: $HASH_URL"
    if ! curl -fsSL "$HASH_URL" -o "$hash_file"; then
        log "ERROR" "Failed to download hash file! Aborting."
        exit 1
    fi

    # Calculate the binary's SHA-256 hash
    local hash
    if command -v sha256sum >/dev/null; then
        hash=$(sha256sum "$binary" | cut -d ' ' -f 1)
    elif command -v shasum >/dev/null; then
        hash=$(shasum -a 256 "$binary" | cut -d ' ' -f 1)
    else
        log "ERROR" "No SHA-256 utility found! Cannot verify binary."
        exit 1
    fi

    log "INFO" "Calculated SHA-256: $hash"

    # Extract expected hash from JSON using grep
    local expected_hash
    expected_hash=$(grep -A 1 '"nym-client"' "$hash_file" | grep -o '"sha256": "[^"]*' | cut -d '"' -f 4)

    log "INFO" "Expected SHA-256: $expected_hash"

    # Compare hashes
    if [[ "$hash" == "$expected_hash" ]]; then
        log "INFO" "✅ Hash verification successful!"
        return 0
    else
        log "ERROR" "❌ Hash verification failed! Binary may be compromised."
        exit 1
    fi
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

    mkdir -p /app/secrets
    chmod 700 /app/secrets  # Restrict access to secrets directory

    if [ ! -f "/app/password.txt" ]; then
        log "ERROR" "password.txt is missing! Please create it before running the install script."
        exit 1
    fi

    log "INFO" "Copying provided password to secrets directory."
    cp "/app/password.txt" "/app/secrets/encryption_password"
    chmod 600 "/app/secrets/encryption_password"

    log "INFO" "Encryption password setup complete."
}

# Generate .env file from .env.example
generate_env_file() {
    log "INFO" "[PHASE] Generating .env file..."
    
    ENV_EXAMPLE=".env.example"
    ENV_FILE=".env"

    if [ ! -f "$ENV_EXAMPLE" ]; then
        log "ERROR" ".env.example not found!"
        exit 1
    fi

    log "INFO" "Copying .env.example to .env"
    cp "$ENV_EXAMPLE" "$ENV_FILE"

    # Extract NYM_CLIENT_ID first
    NYM_CLIENT_ID=$(grep '^NYM_CLIENT_ID=' "$ENV_EXAMPLE" | cut -d '=' -f 2-)
    export NYM_CLIENT_ID

    log "INFO" "Using NYM_CLIENT_ID: $NYM_CLIENT_ID"

    # Replace environment variables using envsubst
    envsubst < "$ENV_EXAMPLE" > "$ENV_FILE"

    chmod 600 "$ENV_FILE"
    log "INFO" ".env file generated successfully."
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
log "INFO" "Client ID: $NYM_CLIENT_ID"
log "INFO" "============================================================="

detect_os
install_dependencies
fetch_latest_version
setup_storage
setup_encryption_password
generate_env_file

# Determine whether to use prebuilt binary or build from source
if [[ "$ARCH" != "x86_64" && "$ARCH" != "x86" ]]; then
    log "INFO" "Forcing build from source due to architecture: $ARCH"
    install_rust
    build_nym_client
    # initialize_nym_client
else
    log "INFO" "Using prebuilt binary for Linux ($ARCH)"
    install_binary
    # initialize_nym_client
fi

log "INFO" "[COMPLETE] Nym client installation & config successful"
