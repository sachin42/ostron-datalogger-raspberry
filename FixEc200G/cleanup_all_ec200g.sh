#!/bin/bash
# Complete EC200G cleanup - removes ALL previous fix attempts

echo "=== EC200G-CN Complete Cleanup ==="
echo ""
echo "This will remove all EC200G fix configurations."
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi
echo ""

REMOVED=0

# Remove old modprobe configs
echo "Checking modprobe configurations..."
for file in /etc/modprobe.d/ec200g*.conf; do
    if [ -f "$file" ]; then
        echo "  Removing: $file"
        sudo rm "$file"
        ((REMOVED++))
    fi
done

# Remove old modules-load configs
echo "Checking modules-load configurations..."
for file in /etc/modules-load.d/ec200g*.conf; do
    if [ -f "$file" ]; then
        echo "  Removing: $file"
        sudo rm "$file"
        ((REMOVED++))
    fi
done

# Remove udev rules
echo "Checking udev rules..."
for file in /etc/udev/rules.d/*ec200g* /etc/udev/rules.d/*quectel*; do
    if [ -f "$file" ]; then
        echo "  Removing: $file"
        sudo rm "$file"
        ((REMOVED++))
    fi
done

# Remove systemd services
echo "Checking systemd services..."
for service in ec200g-boot ec200g-setup ec200g-modem; do
    if systemctl list-unit-files | grep -q "$service.service"; then
        echo "  Disabling and removing: $service.service"
        sudo systemctl disable "$service.service" 2>/dev/null
        sudo rm "/etc/systemd/system/$service.service" 2>/dev/null
        ((REMOVED++))
    fi
done

# Remove helper scripts
echo "Checking helper scripts..."
for script in /usr/local/sbin/ec200g*.sh /usr/local/bin/ec200g*; do
    if [ -f "$script" ]; then
        echo "  Removing: $script"
        sudo rm "$script"
        ((REMOVED++))
    fi
done

# Reload systemd and udev
if [ $REMOVED -gt 0 ]; then
    echo ""
    echo "Reloading system services..."
    sudo systemctl daemon-reload
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "✓ Services reloaded"
fi

echo ""
echo "==================================="
if [ $REMOVED -gt 0 ]; then
    echo "✓ Removed $REMOVED configuration file(s)"
    echo ""
    echo "All EC200G configurations removed."
    echo ""
    echo "Recommended: Reboot to ensure clean state"
    echo "  sudo reboot"
else
    echo "No EC200G configurations found."
fi
