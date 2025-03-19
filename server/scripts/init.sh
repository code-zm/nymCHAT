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

log "INFO" "[COMPLETE] Nym client installation & config successful"
