#!/bin/bash

echo "=== Analog server Service Installation Script ==="

INSTALL_DIR="/home/logger/datalogger/analogserver"
SERVICE_FILE="/etc/systemd/system/analogserver.service"
WRAPPER_SCRIPT="$INSTALL_DIR/analogserver.sh"

# if [ "$EUID" -ne 0 ]; then 
#     echo "ERROR: Please run as root (sudo $0)"
#     exit 1
# fi

echo "Installing systemd service file..."
cp analogserver.service "$SERVICE_FILE"

echo "Installing wrapper script..."
cp analogserver.sh "$WRAPPER_SCRIPT"

echo "Fixing line endings and setting permissions..."
sed -i 's/\r$//' "$WRAPPER_SCRIPT"
chmod +x "$WRAPPER_SCRIPT"
chown logger:logger "$WRAPPER_SCRIPT"

echo "Setting ownership to logger user..."
chown logger:logger "$SERVICE_FILE"

echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Enabling analogserver service to start on boot..."
systemctl enable analogserver.service

echo "Installation complete!"
echo ""
echo "Commands:"
echo "  Start service:  sudo systemctl start analogserver"
echo "  Stop service:   sudo systemctl stop analogserver"
echo "  Restart:        sudo systemctl restart analogserver"
echo "  Check status:   sudo systemctl status analogserver"
echo "  View logs:      sudo journalctl -u analogserver -f"
echo "  Disable on boot: sudo systemctl disable analogserver"
echo ""
echo "The service will start automatically on next reboot."
