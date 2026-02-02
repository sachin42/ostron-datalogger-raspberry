#!/bin/bash
# Immediate EC200G-CN Fix - Run this NOW with modem connected
# This will fix BOTH serial ports AND network interface (usb0)

echo "=== EC200G-CN Immediate Fix ==="
echo "Fixing driver bindings for currently connected modem..."
echo ""

# Check if device is connected
if ! lsusb | grep -q "2c7c:0904"; then
    echo "ERROR: EC200G-CN not detected!"
    echo "Please connect the modem first."
    exit 1
fi

echo "✓ EC200G-CN detected"
echo ""

# Load drivers
echo "Loading drivers..."
sudo modprobe cdc_ether 2>/dev/null
sudo modprobe option 2>/dev/null
echo "✓ Drivers loaded"
echo ""

# Find device path
echo "Finding device path..."
DEVICE_PATH=""
for dev in /sys/bus/usb/devices/*; do
    if [ -f "$dev/idVendor" ] && [ -f "$dev/idProduct" ]; then
        vendor=$(cat "$dev/idVendor" 2>/dev/null)
        product=$(cat "$dev/idProduct" 2>/dev/null)
        if [ "$vendor" = "2c7c" ] && [ "$product" = "0904" ]; then
            DEVICE_PATH=$(basename "$dev")
            echo "✓ Found device at: $DEVICE_PATH"
            break
        fi
    fi
done

if [ -z "$DEVICE_PATH" ]; then
    echo "ERROR: Could not find device path"
    exit 1
fi
echo ""

# Step 1: Unbind interfaces 0,1 from option driver
echo "Step 1: Unbinding CDC Ethernet interfaces from option..."
for iface in 0 1; do
    IFACE_PATH="${DEVICE_PATH}:1.${iface}"
    
    if [ -d "/sys/bus/usb/devices/$IFACE_PATH" ]; then
        if [ -L "/sys/bus/usb/devices/$IFACE_PATH/driver" ]; then
            DRIVER_PATH=$(readlink -f "/sys/bus/usb/devices/$IFACE_PATH/driver")
            DRIVER_NAME=$(basename "$DRIVER_PATH")
            
            if [ "$DRIVER_NAME" = "option" ]; then
                echo "  Unbinding interface $iface from option..."
                sudo sh -c "echo '$IFACE_PATH' > '$DRIVER_PATH/unbind'" 2>/dev/null
                sleep 0.2
            else
                echo "  Interface $iface already on $DRIVER_NAME"
            fi
        fi
    fi
done
echo "✓ Unbinding complete"
echo ""

# Step 2: Bind interfaces 0,1 to cdc_ether
echo "Step 2: Binding CDC Ethernet interfaces to cdc_ether..."
for iface in 0 1; do
    IFACE_PATH="${DEVICE_PATH}:1.${iface}"
    
    if [ -d "/sys/bus/usb/devices/$IFACE_PATH" ]; then
        echo "  Binding interface $iface to cdc_ether..."
        sudo sh -c "echo '$IFACE_PATH' > /sys/bus/usb/drivers/cdc_ether/bind" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "    ✓ Interface $iface bound to cdc_ether"
        else
            echo "    ✗ Failed to bind interface $iface (may already be bound)"
        fi
    fi
done
echo "✓ CDC Ethernet binding complete"
echo ""

# Give it time to settle
echo "Waiting for interfaces to initialize..."
sleep 3
echo ""

# Check results
echo "==================================="
echo "Results:"
echo ""

# Check serial ports
SERIAL_COUNT=$(ls /dev/ttyUSB* 2>/dev/null | wc -l)
if [ $SERIAL_COUNT -gt 0 ]; then
    echo "✓ Serial ports: $SERIAL_COUNT detected"
    ls /dev/ttyUSB* 2>/dev/null | sed 's/^/  /'
else
    echo "✗ Serial ports: None detected"
fi
echo ""

# Check network interface
if ip link show usb0 &>/dev/null; then
    echo "✓ Network interface: usb0 exists"
    ip link show usb0 | grep -E "state|link/ether" | sed 's/^/  /'
    echo ""
    
    # Check if it's UP
    if ip link show usb0 | grep -q "state UP"; then
        echo "  Interface is UP"
    else
        echo "  Interface is DOWN - bringing it up..."
        sudo ip link set usb0 up 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "  ✓ Interface brought up"
        fi
    fi
else
    echo "✗ Network interface: usb0 NOT found"
fi
echo ""

# Show interface driver assignments
echo "Driver assignments:"
for iface in 0 1 2 3 4 5 7 8; do
    IFACE_PATH="${DEVICE_PATH}:1.${iface}"
    
    if [ -d "/sys/bus/usb/devices/$IFACE_PATH" ]; then
        if [ -L "/sys/bus/usb/devices/$IFACE_PATH/driver" ]; then
            DRIVER=$(basename "$(readlink -f /sys/bus/usb/devices/$IFACE_PATH/driver)")
            
            # Check what it should be
            if [ $iface -le 1 ]; then
                EXPECTED="cdc_ether"
            else
                EXPECTED="option"
            fi
            
            if [ "$DRIVER" = "$EXPECTED" ]; then
                echo "  Interface $iface: $DRIVER ✓"
            else
                echo "  Interface $iface: $DRIVER (expected $EXPECTED) ✗"
            fi
        else
            echo "  Interface $iface: NO DRIVER ✗"
        fi
    fi
done
echo ""

# Summary
echo "==================================="
if [ $SERIAL_COUNT -ge 5 ] && ip link show usb0 &>/dev/null; then
    echo "✓ SUCCESS: Both serial ports AND network working!"
    echo ""
    echo "Test serial with:"
    echo "  sudo minicom -D /dev/ttyUSB2"
    echo ""
    echo "Test network with:"
    echo "  sudo ip link set usb0 up"
    echo "  sudo dhclient usb0"
    echo ""
    echo "To make this permanent, run:"
    echo "  ./fix_ec200g_complete.sh"
elif [ $SERIAL_COUNT -ge 5 ]; then
    echo "⚠ PARTIAL: Serial ports work but no network interface"
    echo ""
    echo "Try unplugging and replugging the modem, then run this script again"
elif ip link show usb0 &>/dev/null; then
    echo "⚠ PARTIAL: Network interface exists but few/no serial ports"
    echo ""
    echo "Try unplugging and replugging the modem, then run this script again"
else
    echo "✗ FAILED: Neither serial nor network working properly"
    echo ""
    echo "Try:"
    echo "1. Unplug the modem"
    echo "2. Wait 5 seconds"  
    echo "3. Plug it back in"
    echo "4. Run this script again"
fi
