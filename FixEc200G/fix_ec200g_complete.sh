#!/bin/bash
# EC200G-CN Complete Fix - Handles both serial ports AND network interface
# This version ensures cdc_ether gets interfaces 0,1 and option gets 2,3,4,5,7,8

echo "=== EC200G-CN Complete Fix (Serial + Network) ==="
echo ""

# 1. Create a helper script that properly assigns drivers
echo "Step 1: Creating driver assignment script..."
sudo tee /usr/local/sbin/ec200g-bind-drivers.sh > /dev/null << 'EOF'
#!/bin/bash
# Properly bind EC200G interfaces to correct drivers

# Wait for device to settle
sleep 2

# Find the EC200G device
DEVICE_PATH=""
for dev in /sys/bus/usb/devices/*; do
    if [ -f "$dev/idVendor" ] && [ -f "$dev/idProduct" ]; then
        vendor=$(cat "$dev/idVendor" 2>/dev/null)
        product=$(cat "$dev/idProduct" 2>/dev/null)
        if [ "$vendor" = "2c7c" ] && [ "$product" = "0904" ]; then
            DEVICE_PATH=$(basename "$dev")
            logger "EC200G: Found device at $DEVICE_PATH"
            break
        fi
    fi
done

if [ -z "$DEVICE_PATH" ]; then
    logger "EC200G: Device not found"
    exit 0
fi

# Function to unbind an interface from current driver
unbind_interface() {
    local iface=$1
    local iface_path="${DEVICE_PATH}:1.${iface}"
    
    if [ -d "/sys/bus/usb/devices/$iface_path" ]; then
        if [ -L "/sys/bus/usb/devices/$iface_path/driver" ]; then
            local driver_path=$(readlink -f "/sys/bus/usb/devices/$iface_path/driver")
            echo "$iface_path" > "$driver_path/unbind" 2>/dev/null
            logger "EC200G: Unbound interface $iface"
        fi
    fi
}

# Function to bind an interface to a specific driver
bind_interface() {
    local iface=$1
    local driver=$2
    local iface_path="${DEVICE_PATH}:1.${iface}"
    
    if [ -d "/sys/bus/usb/devices/$iface_path" ]; then
        echo "$iface_path" > "/sys/bus/usb/drivers/$driver/bind" 2>/dev/null
        if [ $? -eq 0 ]; then
            logger "EC200G: Bound interface $iface to $driver"
        fi
    fi
}

# Step 1: Unbind interfaces 0,1 from option (if bound)
logger "EC200G: Unbinding CDC Ethernet interfaces from option..."
unbind_interface 0
unbind_interface 1
sleep 0.5

# Step 2: Bind interfaces 0,1 to cdc_ether
logger "EC200G: Binding CDC Ethernet interfaces..."
bind_interface 0 cdc_ether
bind_interface 1 cdc_ether
sleep 0.5

# Step 3: Ensure serial interfaces are bound to option
logger "EC200G: Checking serial interfaces..."
for iface in 2 3 4 5 7 8; do
    iface_path="${DEVICE_PATH}:1.${iface}"
    if [ -d "/sys/bus/usb/devices/$iface_path" ]; then
        if [ ! -L "/sys/bus/usb/devices/$iface_path/driver" ]; then
            bind_interface $iface option
        fi
    fi
done

logger "EC200G: Driver binding complete"
EOF

sudo chmod +x /usr/local/sbin/ec200g-bind-drivers.sh
echo "✓ Created driver binding script"
echo ""

# 2. Create udev rule that triggers proper binding
echo "Step 2: Creating udev rules..."
sudo tee /etc/udev/rules.d/98-ec200g-complete.rules > /dev/null << 'EOF'
# EC200G-CN Complete Support (Serial + Network)

# Load drivers when device is added
ACTION=="add", SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", \
    ATTRS{idVendor}=="2c7c", ATTRS{idProduct}=="0904", \
    RUN+="/bin/sh -c 'modprobe cdc_ether; modprobe option; echo 2c7c 0904 > /sys/bus/usb-serial/drivers/option1/new_id 2>/dev/null || true'"

# After device settles, fix the driver bindings
ACTION=="add", SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", \
    ATTRS{idVendor}=="2c7c", ATTRS{idProduct}=="0904", \
    RUN+="/bin/sh -c 'sleep 3; /usr/local/sbin/ec200g-bind-drivers.sh &'"

# Set permissions
SUBSYSTEM=="tty", ATTRS{idVendor}=="2c7c", ATTRS{idProduct}=="0904", \
    MODE="0666", GROUP="dialout"

SUBSYSTEM=="net", ATTRS{idVendor}=="2c7c", ATTRS{idProduct}=="0904", \
    MODE="0666"
EOF

echo "✓ Created udev rules"
echo ""

# 3. Create boot-time service
echo "Step 3: Creating boot service..."
sudo tee /etc/systemd/system/ec200g-boot.service > /dev/null << 'EOF'
[Unit]
Description=EC200G-CN Boot Setup
After=systemd-modules-load.service
Before=network-pre.target
DefaultDependencies=no

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'modprobe cdc_ether; modprobe option; sleep 1; echo 2c7c 0904 > /sys/bus/usb-serial/drivers/option1/new_id 2>/dev/null || true'
RemainAfterExit=yes

[Install]
WantedBy=sysinit.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ec200g-boot.service
echo "✓ Service enabled"
echo ""

# 4. Reload udev
echo "Step 4: Reloading udev..."
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "✓ Udev reloaded"
echo ""

# 5. Create manual rebind script for testing
echo "Step 5: Creating manual rebind script..."
sudo tee /usr/local/bin/ec200g-rebind > /dev/null << 'EOF'
#!/bin/bash
# Manually fix EC200G driver bindings

echo "Fixing EC200G-CN driver bindings..."

# Load drivers
modprobe cdc_ether 2>/dev/null
modprobe option 2>/dev/null

# Add device ID if not already added
echo 2c7c 0904 > /sys/bus/usb-serial/drivers/option1/new_id 2>/dev/null || true

# Run the binding script
/usr/local/sbin/ec200g-bind-drivers.sh

echo "Done. Check with:"
echo "  ls /dev/ttyUSB*"
echo "  ip link show usb0"
EOF

sudo chmod +x /usr/local/bin/ec200g-rebind
echo "✓ Created manual rebind tool"
echo ""

echo "==================================="
echo "Installation complete!"
echo ""
echo "IMPORTANT: The modem is currently connected."
echo "To apply the fix to the current connection:"
echo ""
echo "  sudo ec200g-rebind"
echo ""
echo "This will fix BOTH serial ports AND network (usb0)."
echo ""
echo "After running ec200g-rebind, verify:"
echo "  ls /dev/ttyUSB*    (should show ttyUSB2-7)"
echo "  ip link show usb0   (should show usb0 interface)"
echo ""
echo "For future connections (after reboot), the fix will apply automatically."
echo ""
read -p "Run ec200g-rebind now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    sudo ec200g-rebind
    echo ""
    echo "Waiting 3 seconds for interfaces to appear..."
    sleep 3
    echo ""
    echo "Serial ports:"
    ls -l /dev/ttyUSB* 2>/dev/null || echo "  No serial ports found"
    echo ""
    echo "Network interface:"
    ip link show usb0 2>/dev/null || echo "  usb0 not found"
fi
