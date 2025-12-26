#!/bin/bash

echo "=== DataLogger Service Installation Script ==="

INSTALL_DIR="/home/logger/datalogger"
SERVICE_FILE="/etc/systemd/system/datalogger.service"
WRAPPER_SCRIPT="$INSTALL_DIR/datalogger-wrapper.sh"

if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run as root (sudo $0)"
    exit 1
fi

echo "Installing systemd service file..."
cp datalogger.service "$SERVICE_FILE"

echo "Installing wrapper script..."
cp datalogger-wrapper.sh "$WRAPPER_SCRIPT"
chmod +x "$WRAPPER_SCRIPT"

echo "Setting ownership to logger user..."
chown logger:logger "$SERVICE_FILE" "$WRAPPER_SCRIPT"

echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Enabling datalogger service to start on boot..."
systemctl enable datalogger.service

echo "Installation complete!"
echo ""
echo "Commands:"
echo "  Start service:  sudo systemctl start datalogger"
echo "  Stop service:   sudo systemctl stop datalogger"
echo "  Restart:        sudo systemctl restart datalogger"
echo "  Check status:   sudo systemctl status datalogger"
echo "  View logs:      sudo journalctl -u datalogger -f"
echo "  Disable on boot: sudo systemctl disable datalogger"
echo ""
echo "The service will start automatically on next reboot."
