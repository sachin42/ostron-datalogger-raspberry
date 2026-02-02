#!/bin/bash
# Quick fix - Bind serial interfaces to option driver
# Run this when network (usb0) exists but serial ports are missing

echo "=== Binding Serial Interfaces to Option Driver ==="
echo ""

# Check device
if ! lsusb | grep -q "2c7c:0904"; then
    echo "ERROR: EC200G-CN not detected!"
    exit 1
fi
echo "✓ EC200G-CN detected"
echo ""

# Load option driver
echo "Loading option driver..."
sudo modprobe option
sudo modprobe usbserial
echo "✓ Loaded"
echo ""

# Register device ID
echo "Registering device with option..."
sudo sh -c 'echo 2c7c 0904 > /sys/bus/usb-serial/drivers/option1/new_id' 2>/dev/null || echo "(already registered)"
echo "✓ Registered"
echo ""

# Find device
DEVICE_PATH=""
for dev in /sys/bus/usb/devices/*; do
    if [ -f "$dev/idVendor" ] && [ -f "$dev/idProduct" ]; then
        vendor=$(cat "$dev/idVendor" 2>/dev/null)
        product=$(cat "$dev/idProduct" 2>/dev/null)
        if [ "$vendor" = "2c7c" ] && [ "$product" = "0904" ]; then
            DEVICE_PATH=$(basename "$dev")
            break
        fi
    fi
done

if [ -z "$DEVICE_PATH" ]; then
    echo "ERROR: Could not find device"
    exit 1
fi
echo "Device path: $DEVICE_PATH"
echo ""

# Bind serial interfaces (2,3,4,5,7,8) to option
echo "Binding serial interfaces to option driver..."
SUCCESS=0
for iface in 2 3 4 5 7 8; do
    IFACE_PATH="${DEVICE_PATH}:1.${iface}"
    
    if [ -d "/sys/bus/usb/devices/$IFACE_PATH" ]; then
        echo -n "  Interface $iface: "
        
        if sudo sh -c "echo '$IFACE_PATH' > /sys/bus/usb/drivers/option/bind" 2>/dev/null; then
            echo "✓ Bound to option"
            ((SUCCESS++))
        else
            echo "✗ Failed (may already be bound or error)"
        fi
    else
        echo "  Interface $iface: Does not exist"
    fi
done
echo ""

# Wait for ttyUSB devices to appear
echo "Waiting for serial ports..."
sleep 2
echo ""

# Check results
SERIAL_COUNT=$(ls /dev/ttyUSB* 2>/dev/null | wc -l)
echo "==================================="
if [ $SERIAL_COUNT -gt 0 ]; then
    echo "✓ SUCCESS! Found $SERIAL_COUNT serial port(s):"
    ls /dev/ttyUSB*
    echo ""
    
    if ip link show usb0 &>/dev/null; then
        echo "✓ Network interface usb0 also exists"
        echo ""
        echo "✓✓✓ BOTH serial AND network working! ✓✓✓"
    fi
else
    echo "✗ No serial ports found"
    echo ""
    echo "Debug info:"
    for iface in 2 3 4 5 7 8; do
        IFACE_PATH="${DEVICE_PATH}:1.${iface}"
        if [ -d "/sys/bus/usb/devices/$IFACE_PATH" ]; then
            if [ -L "/sys/bus/usb/devices/$IFACE_PATH/driver" ]; then
                DRIVER=$(basename "$(readlink -f /sys/bus/usb/devices/$IFACE_PATH/driver)")
                echo "  Interface $iface: $DRIVER"
            else
                echo "  Interface $iface: NO DRIVER"
            fi
        fi
    done
fi
