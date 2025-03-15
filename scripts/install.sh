#!/bin/bash
set -e

NYM_BINARY_URL="https://github.com/nymtech/nym/releases/download/nym-binaries-v2025.4-dorina-patched/nym-client"
CLIENT_ID=${NYM_CLIENT_ID:-"nymserver"}
ENV_FILE="/app/.env"
ENV_EXAMPLE="/app/.env.example"
PASSWORD_FILE="/app/secrets/encryption_password"
HOST_PASSWORD_FILE="/app/password.txt"  # Where password.txt is expected before copying
STORAGE_DIR="/app/storage"
NYM_CONFIG_DIR="/root/.nym"

# Install dependencies
install_dependencies() {
    echo "[PHASE] Installing required packages..."
    apt-get update && apt-get install -y curl
}

# Install the Nym client binary in /app/
install_binary() {
    echo "[PHASE] Installing Nym client binary..."
    INSTALL_PATH="/app/nym-client"

    if [ -f "$INSTALL_PATH" ]; then
        echo "[INFO] Using existing binary"
        return
    fi

    echo "[INFO] Downloading Nym client from $NYM_BINARY_URL"
    curl -L "$NYM_BINARY_URL" -o "$INSTALL_PATH"
    chmod +x "$INSTALL_PATH"
    echo "[INFO] Nym client installed in /app/"
}

# Ensure storage directories exist and have correct permissions
setup_storage() {
    echo "[PHASE] Setting up storage directories..."
    
    mkdir -p "$STORAGE_DIR"
    chmod -R 777 "$STORAGE_DIR"  # Ensure all users can write logs

    mkdir -p /app/secrets
    chmod -R 700 /app/secrets  # Only allow root to read secrets

    mkdir -p "$NYM_CONFIG_DIR"
    chmod -R 700 "$NYM_CONFIG_DIR"

    echo "[INFO] Storage directories are set up."
}

# Copy encryption password
setup_encryption_password() {
    echo "[PHASE] Setting up encryption password..."
    
    if [ ! -f "/app/secrets/encryption_password" ]; then
        if [ -f "/app/password.txt" ]; then
            echo "[INFO] Copying encryption password into /app/secrets/"
            mkdir -p /app/secrets
            cp "/app/password.txt" "/app/secrets/encryption_password"
        else
            echo "[WARNING] No password.txt found! Generating a random encryption password."
            mkdir -p /app/secrets
            openssl rand -base64 32 > "/app/secrets/encryption_password"
        fi
        chmod 600 "/app/secrets/encryption_password"
        echo "[INFO] Encryption password successfully set up in /app/secrets/"
    else
        echo "[INFO] Encryption password already exists in /app/secrets/. Skipping setup."
    fi
}



# Generate .env file from .env.example
generate_env_file() {
    echo "[PHASE] Generating .env file..."
    
    if [ ! -f "$ENV_EXAMPLE" ]; then
        echo "[ERROR] .env.example not found in /app!"
        exit 1
    fi

    # Replace placeholders and create .env
    sed "s/{NYM_CLIENT_ID}/$CLIENT_ID/g" "$ENV_EXAMPLE" > "$ENV_FILE"

    chmod 600 "$ENV_FILE"  # Restrict access for security
    echo "[INFO] .env file created at $ENV_FILE"
}

# Main execution flow
echo "============================================================="
echo "NYM CLIENT INSTALLATION AND CONFIGURATION"
echo "Client ID: $CLIENT_ID"
echo "============================================================="

install_dependencies
install_binary
setup_storage
setup_encryption_password
generate_env_file

echo "[COMPLETE] Nym client installation successful"

