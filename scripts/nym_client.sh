#!/bin/bash
set -e

NYM_BINARY_URL="https://github.com/nymtech/nym/releases/download/nym-binaries-v2025.4-dorina-patched/nym-client"
SYSTEMD_SERVICE_NAME="nym-client-${NYM_CLIENT_ID}"
NYM_USER="nym"
NYM_HOME="/home/$NYM_USER"

# Function to prompt user for .env values and set up .env file
setup_env_file() {
    REAL_USER=$(logname)
    REAL_HOME=$(eval echo ~$REAL_USER)
    ENV_FILE="$REAL_HOME/.env"
    
    echo "[PHASE] Setting up .env file..."
    
    read -p "Enter NYM_CLIENT_ID (default: nym_client): " NYM_CLIENT_ID
    NYM_CLIENT_ID=${NYM_CLIENT_ID:-nym_client}
    read -p "Enter DATABASE_PATH (default: storage/${NYM_CLIENT_ID}.db): " DATABASE_PATH
    DATABASE_PATH=${DATABASE_PATH:-storage/${NYM_CLIENT_ID}.db}
    read -p "Enter LOG_FILE_PATH (default: storage/app.log): " LOG_FILE_PATH
    LOG_FILE_PATH=${LOG_FILE_PATH:-storage/app.log}
    read -p "Enter KEYS_DIR (default: storage/keys): " KEYS_DIR
    KEYS_DIR=${KEYS_DIR:-storage/keys}
    read -p "Enter WEBSOCKET_URL (default: ws://127.0.0.1:1977): " WEBSOCKET_URL
    WEBSOCKET_URL=${WEBSOCKET_URL:-ws://127.0.0.1:1977}
    read -p "Enter SERVER_USERNAME (default: ${NYM_CLIENT_ID}): " SERVER_USERNAME
    SERVER_USERNAME=${SERVER_USERNAME:-$NYM_CLIENT_ID}
    
    cat > "$ENV_FILE" << EOF
NYM_CLIENT_ID=$NYM_CLIENT_ID
DATABASE_PATH=$DATABASE_PATH
LOG_FILE_PATH=$LOG_FILE_PATH
KEYS_DIR=$KEYS_DIR
WEBSOCKET_URL=$WEBSOCKET_URL
SERVER_USERNAME=$SERVER_USERNAME
EOF
    
    echo "[INFO] .env file created at $ENV_FILE"
    export $(grep -v '^#' "$ENV_FILE" | xargs)
}

# Function to check if script is run with sudo/root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo "[CRITICAL] This script requires root privileges for system modifications."
        exit 1
    fi
}

# Function to check for port conflict
check_port_availability() {
    if netstat -tuln | grep -q ":1977 "; then
        echo "[FATAL] Port 1977 is already in use. Nym client requires exclusive access to this port."
        exit 1
    fi
}

# Function to check architecture
check_architecture() {
    ARCH=$(uname -m)
    if [ "$ARCH" != "x86_64" ]; then
        echo "[FATAL] Unsupported architecture: $ARCH"
        exit 1
    fi
}

# Function to set up Nym user account
setup_nym_user() {
    echo "[PHASE] Setting up Nym service account..."
    if ! id -u $NYM_USER >/dev/null 2>&1; then
        echo "[INFO] Creating system user '$NYM_USER'"
        useradd -r -m -d $NYM_HOME -s /usr/sbin/nologin $NYM_USER
    fi
}

# Function to install Nym binary
install_binary() {
    echo "[PHASE] Installing Nym client binary..."
    INSTALL_PATH="/usr/local/bin/nym-client"
    curl -L "$NYM_BINARY_URL" -o /tmp/nym-client
    chmod +x /tmp/nym-client
    mv /tmp/nym-client "$INSTALL_PATH"
}

# Function to initialize Nym client
initialize_client() {
    echo "[PHASE] Initializing Nym client configuration..."
    NYM_CONFIG_DIR="$NYM_HOME/.nym/clients/$NYM_CLIENT_ID"
    
    if [ ! -d "$NYM_CONFIG_DIR" ]; then
        sudo -u $NYM_USER nym-client init --id "$NYM_CLIENT_ID"
    fi
    
    chown -R $NYM_USER:$NYM_USER "$NYM_HOME/.nym"
}

# Function to set up systemd service
setup_systemd_service() {
    echo "[PHASE] Setting up systemd service..."
    SERVICE_FILE="/etc/systemd/system/$SYSTEMD_SERVICE_NAME.service"
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Nym Client ($NYM_CLIENT_ID)
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=5
User=$NYM_USER
ExecStart=/usr/local/bin/nym-client run --id "$NYM_CLIENT_ID"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable "$SYSTEMD_SERVICE_NAME"
}

# Function to start the service
start_service() {
    echo "[PHASE] Starting Nym client service..."
    systemctl start "$SYSTEMD_SERVICE_NAME"
}

# Main execution flow
echo "============================================================="
echo "NYM CLIENT INSTALLATION AND CONFIGURATION"
echo "============================================================="

setup_env_file
check_root
check_port_availability
check_architecture
setup_nym_user
install_binary
initialize_client
setup_systemd_service
start_service

echo "[COMPLETE] Nym client installation successful"