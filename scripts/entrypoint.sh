#!/bin/bash
set -e

# Ensure correct storage location
export NYM_CONFIG_DIR="/root/.nym"

# Load environment variables from .env safely
if [ -f "/app/.env" ]; then
    echo "[INFO] Loading environment variables from .env"
    set -a
    source /app/.env
    set +a
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

# Ensure Nym client is initialized
if [ ! -d "/root/.nym/clients/$NYM_CLIENT_ID" ]; then
    echo "[INFO] No existing Nym config found. Initializing..."
    /app/nym-client init --id "$NYM_CLIENT_ID"
else
    echo "[INFO] Existing Nym config found. Skipping init."
fi

# Start Nym client in the background
echo "[INFO] Starting Nym client..."
/app/nym-client run --id "$NYM_CLIENT_ID" &

# Allow some time for Nym to start
sleep 5

# Run the main Python application
exec python server/mainApp.py
