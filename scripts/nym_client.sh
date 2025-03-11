#!/bin/bash
set -e

NYM_BINARY_URL="https://github.com/nymtech/nym/releases/download/nym-binaries-v2025.4-dorina-patched/nym-client"
CLIENT_ID=${NYM_CLIENT_ID:-"nymserver"}
SYSTEMD_SERVICE_NAME="nym-client-${CLIENT_ID}"
NYM_USER="nym"
NYM_HOME="/home/$NYM_USER"

# Function to check if script is run with sudo/root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo "[CRITICAL] This script requires root privileges for system modifications."
        exit 1
    fi
}

# Check for port conflict - fail early
check_port_availability() {
    if netstat -tuln | grep -q ":1977 "; then
        echo "[FATAL] Port 1977 is already in use. Nym client requires exclusive access to this port."
        echo "[INFO] Run 'netstat -tuln | grep :1977' to identify the conflicting process."
        exit 1
    fi
}

# Check architecture
check_architecture() {
    ARCH=$(uname -m)
    if [ "$ARCH" != "x86_64" ]; then
        echo "[FATAL] Unsupported architecture: $ARCH"
        echo "[INFO] This script only supports x86_64 architecture for the specified Nym binary."
        exit 1
    fi
}

# Create Nym user account if it doesn't exist
setup_nym_user() {
    echo "[PHASE] Setting up Nym service account..."
    if ! id -u $NYM_USER >/dev/null 2>&1; then
        echo "[WARN] Creating system user '$NYM_USER' with home directory '$NYM_HOME'"
        echo -n "[INPUT] Do you approve this system modification? (y/n): "
        read -r APPROVE
        if [[ ! "$APPROVE" =~ ^[Yy]$ ]]; then
            echo "[ABORT] User creation aborted."
            exit 1
        fi
        useradd -r -m -d $NYM_HOME -s /usr/sbin/nologin $NYM_USER
        echo "[INFO] Created system user '$NYM_USER'"
    else
        echo "[INFO] User '$NYM_USER' already exists"
    fi
}

# Install the Nym binary
install_binary() {
    echo "[PHASE] Installing Nym client binary..."
    INSTALL_PATH="/usr/local/bin/nym-client"
    
    if [ -f "$INSTALL_PATH" ]; then
        echo "[WARN] Nym client binary already exists at $INSTALL_PATH"
        echo -n "[INPUT] Replace existing binary? (y/n): "
        read -r REPLACE
        if [[ ! "$REPLACE" =~ ^[Yy]$ ]]; then
            echo "[INFO] Using existing binary"
            return
        fi
    fi
    
    echo "[INFO] Downloading Nym client from $NYM_BINARY_URL"
    curl -L "$NYM_BINARY_URL" -o /tmp/nym-client
    chmod +x /tmp/nym-client
    mv /tmp/nym-client "$INSTALL_PATH"
    echo "[INFO] Nym client installed to $INSTALL_PATH"
}

# Initialize the client if needed
initialize_client() {
    echo "[PHASE] Initializing Nym client configuration..."
    NYM_CONFIG_DIR="$NYM_HOME/.nym/clients/$CLIENT_ID"
    
    if [ -d "$NYM_CONFIG_DIR" ]; then
        echo "[WARN] Nym client configuration for '$CLIENT_ID' already exists"
        echo "[INFO] Location: $NYM_CONFIG_DIR"
        echo "[INFO] Preserving existing configuration"
    else
        echo "[INFO] Initializing new client with ID: $CLIENT_ID"
        sudo -u $NYM_USER nym-client init --id "$CLIENT_ID"
        echo "[INFO] Client initialized at: $NYM_CONFIG_DIR"
    fi
    
    # Ensure correct permissions
    chown -R $NYM_USER:$NYM_USER "$NYM_HOME/.nym"
}

# Create systemd service
setup_systemd_service() {
    echo "[PHASE] Setting up systemd service..."
    SERVICE_FILE="/etc/systemd/system/$SYSTEMD_SERVICE_NAME.service"
    
    if [ -f "$SERVICE_FILE" ]; then
        echo "[WARN] Systemd service already exists: $SERVICE_FILE"
        echo -n "[INPUT] Replace existing service configuration? (y/n): "
        read -r REPLACE
        if [[ ! "$REPLACE" =~ ^[Yy]$ ]]; then
            echo "[INFO] Using existing service configuration"
            return
        fi
    fi
    
    echo "[INFO] Creating systemd service: $SYSTEMD_SERVICE_NAME"
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Nym Client ($CLIENT_ID)
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=5
User=$NYM_USER
ExecStart=/usr/local/bin/nym-client run --id "$CLIENT_ID"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    echo "[INFO] Reloading systemd daemon"
    systemctl daemon-reload
    echo "[INFO] Enabling $SYSTEMD_SERVICE_NAME service"
    systemctl enable "$SYSTEMD_SERVICE_NAME"
}

# Start the service
start_service() {
    echo "[PHASE] Starting Nym client service..."
    
    if systemctl is-active --quiet "$SYSTEMD_SERVICE_NAME"; then
        echo "[INFO] Restarting service: $SYSTEMD_SERVICE_NAME"
        systemctl restart "$SYSTEMD_SERVICE_NAME"
    else
        echo "[INFO] Starting service: $SYSTEMD_SERVICE_NAME"
        systemctl start "$SYSTEMD_SERVICE_NAME"
    fi
    
    # Verify service status
    if systemctl is-active --quiet "$SYSTEMD_SERVICE_NAME"; then
        echo "[SUCCESS] Nym client service running successfully"
    else
        echo "[FATAL] Service failed to start"
        echo "[DEBUG] Service logs: journalctl -u $SYSTEMD_SERVICE_NAME"
        exit 1
    fi
}

# Display service status
show_service_info() {
    echo "[PHASE] Service Information:"
    echo "[INFO] Service name: $SYSTEMD_SERVICE_NAME"
    echo "[INFO] Status command: systemctl status $SYSTEMD_SERVICE_NAME"
    echo "[INFO] Logs command: journalctl -u $SYSTEMD_SERVICE_NAME -f"
    echo "[INFO] Binary path: /usr/local/bin/nym-client"
    echo "[INFO] Config path: $NYM_HOME/.nym/clients/$CLIENT_ID"
    echo "[INFO] Nym user: $NYM_USER"
    echo "[INFO] Service controlled by systemd"
}

# Main execution flow
echo "============================================================="
echo "NYM CLIENT INSTALLATION AND CONFIGURATION"
echo "Client ID: $CLIENT_ID"
echo "============================================================="

check_root
check_port_availability
check_architecture
setup_nym_user
install_binary
initialize_client
setup_systemd_service
start_service
show_service_info

echo "[COMPLETE] Nym client installation successful"
