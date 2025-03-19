#!/bin/bash
set -e

# Ensure correct storage location
export NYM_CONFIG_DIR="/root/.nym"

# Check for encryption password
if [ ! -f "/app/secrets/encryption_password" ]; then
    echo "[ERROR] Encryption password secret not found!"
    exit 1
fi
chmod 600 /app/secrets/encryption_password
echo "[INFO] Encryption password loaded successfully."

# Ensure Nym client is initialized
if [ ! -d "/root/.nym/clients/$NYM_CLIENT_ID" ]; then
    echo "[INFO] No existing Nym client found. Initializing..."
    /app/nym-client init --id "$NYM_CLIENT_ID" --host 0.0.0.0
else
    echo "[INFO] Existing Nym client found. Skipping init."
fi

# Run the main Python application **as the main process**
exec python server/mainApp.py
