#!/bin/bash
set -e

# Ensure correct storage location
export NYM_CONFIG_DIR="/root/.nym"

# Load environment variables from .env
if [ -f "/app/.env" ]; then
    echo "[INFO] Loading environment variables from .env"
    export $(grep -v '^#' /app/.env | xargs)
else
    echo "[WARNING] .env file not found! Using defaults."
fi

# Check for encryption password
if [ ! -f "/app/secrets/encryption_password" ]; then
    echo "[ERROR] Encryption password secret not found!"
    exit 1
fi
chmod 600 /app/secrets/encryption_password
echo "[INFO] Encryption password loaded successfully."

# Initialize Nym client if needed
if [ ! -d "/root/.nym/clients/$NYM_CLIENT_ID" ]; then
    echo "[INFO] No existing Nym config found. Initializing..."
    ./nym-client init --id "$NYM_CLIENT_ID"
else
    echo "[INFO] Existing Nym config found. Skipping init."
fi

# Start Nym client in the background
./nym-client run --id "$NYM_CLIENT_ID" &

sleep 5

exec python server/mainApp.py
