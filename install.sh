#!/bin/bash
# WoL Game Server Proxy Installation Script
# This script installs the WoL proxy service on Debian-based systems

set -e

# Configuration
INSTALL_DIR="/opt/wol-proxy"
CONFIG_DIR="/etc/wol-proxy"
LOG_DIR="/var/log"
SERVICE_USER="wol-proxy"
SERVICE_FILE="wol-proxy.service"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Install system dependencies
install_dependencies() {
    log_info "Installing system dependencies..."
    
    apt-get update
    apt-get install -y \\
        python3 \\
        python3-pip \\
        python3-venv \\
        curl \\
        iputils-arping \\
        iproute2 \\
        sudo
    
    log_info "System dependencies installed"
}

# Create service user
create_user() {
    log_info "Creating service user: $SERVICE_USER"
    
    if id "$SERVICE_USER" &>/dev/null; then
        log_warn "User $SERVICE_USER already exists"
    else
        useradd --system --home-dir "$INSTALL_DIR" --shell /bin/false "$SERVICE_USER"
        log_info "User $SERVICE_USER created"
    fi
}

# Create directories
create_directories() {
    log_info "Creating directories..."
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$(dirname "$LOG_DIR/wol-proxy.log")"
    
    log_info "Directories created"
}

# Install application
install_application() {
    log_info "Installing application files..."
    
    # Copy application files
    cp -r src/ "$INSTALL_DIR/"
    cp main.py "$INSTALL_DIR/"
    cp requirements.txt "$INSTALL_DIR/"
    
    # Set permissions
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    chmod +x "$INSTALL_DIR/main.py"
    
    log_info "Application files installed"
}

# Create Python virtual environment
create_venv() {
    log_info "Creating Python virtual environment..."
    
    sudo -u "$SERVICE_USER" python3 -m venv "$INSTALL_DIR/venv"
    
    # Upgrade pip and install dependencies
    sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
    
    log_info "Virtual environment created and dependencies installed"
}

# Setup configuration
setup_configuration() {
    log_info "Setting up configuration..."
    
    if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
        # Generate example config
        sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/main.py" --create-config
        mv config.json.example "$CONFIG_DIR/config.json"
        
        log_warn "Default configuration created at $CONFIG_DIR/config.json"
        log_warn "Please edit this file with your server details before starting the service"
    else
        log_info "Configuration file already exists at $CONFIG_DIR/config.json"
    fi
    
    # Set permissions
    chown root:root "$CONFIG_DIR/config.json"
    chmod 644 "$CONFIG_DIR/config.json"
}

# Setup sudo permissions for IP management
setup_sudo() {
    log_info "Setting up sudo permissions for IP management..."
    
    cat > /etc/sudoers.d/wol-proxy << EOF
# WoL Proxy - Allow IP address management
$SERVICE_USER ALL=(ALL) NOPASSWD: /sbin/ip addr add *, /sbin/ip addr del *
EOF
    
    chmod 440 /etc/sudoers.d/wol-proxy
    
    log_info "Sudo permissions configured"
}

# Install systemd service
install_service() {
    log_info "Installing systemd service..."
    
    cp "$SERVICE_FILE" /etc/systemd/system/
    chmod 644 "/etc/systemd/system/$SERVICE_FILE"
    
    systemctl daemon-reload
    systemctl enable "$SERVICE_FILE"
    
    log_info "Systemd service installed and enabled"
}

# Setup logging
setup_logging() {
    log_info "Setting up logging..."
    
    # Create log file
    touch "$LOG_DIR/wol-proxy.log"
    chown "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR/wol-proxy.log"
    chmod 644 "$LOG_DIR/wol-proxy.log"
    
    # Setup log rotation
    cat > /etc/logrotate.d/wol-proxy << EOF
$LOG_DIR/wol-proxy.log {
    weekly
    rotate 4
    missingok
    notifempty
    compress
    delaycompress
    create 644 $SERVICE_USER $SERVICE_USER
    postrotate
        systemctl reload-or-restart wol-proxy.service > /dev/null 2>&1 || true
    endscript
}
EOF
    
    log_info "Logging configured"
}

# Validate installation
validate_installation() {
    log_info "Validating installation..."
    
    # Check if config is valid
    if sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/main.py" --config "$CONFIG_DIR/config.json" --validate-config &>/dev/null; then
        log_info "Configuration validation passed"
    else
        log_warn "Configuration validation failed - please check $CONFIG_DIR/config.json"
    fi
    
    # Check service status
    if systemctl is-enabled wol-proxy.service &>/dev/null; then
        log_info "Service is enabled"
    else
        log_error "Service is not enabled"
    fi
    
    log_info "Installation validation complete"
}

# Print post-installation instructions
print_instructions() {
    echo
    log_info "Installation complete!"
    echo
    echo "Next steps:"
    echo "1. Edit the configuration file: $CONFIG_DIR/config.json"
    echo "   - Set your game server IP address and MAC address"
    echo "   - Configure game-specific settings"
    echo "   - Adjust timing parameters as needed"
    echo
    echo "2. Validate your configuration:"
    echo "   sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/python $INSTALL_DIR/main.py --config $CONFIG_DIR/config.json --validate-config"
    echo
    echo "3. Start the service:"
    echo "   systemctl start wol-proxy.service"
    echo
    echo "4. Check service status:"
    echo "   systemctl status wol-proxy.service"
    echo
    echo "5. View logs:"
    echo "   journalctl -u wol-proxy.service -f"
    echo "   tail -f $LOG_DIR/wol-proxy.log"
    echo
    echo "Configuration file location: $CONFIG_DIR/config.json"
    echo "Installation directory: $INSTALL_DIR"
    echo "Log file: $LOG_DIR/wol-proxy.log"
    echo
}

# Main installation function
main() {
    log_info "Starting WoL Game Server Proxy installation..."
    
    check_root
    install_dependencies
    create_user
    create_directories
    install_application
    create_venv
    setup_configuration
    setup_sudo
    install_service
    setup_logging
    validate_installation
    print_instructions
    
    log_info "Installation completed successfully!"
}

# Run installation
main "$@"