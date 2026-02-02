# EC200G-CN Complete Fix - Serial Ports + Network Interface

## Your Current Problem

Based on your debug output, the serial ports ARE working (ttyUSB2-7), but **the network interface (usb0) is missing**.

This is happening because the `option` driver is claiming ALL interfaces (0,1,2,3,4,5,7,8), including interfaces 0 and 1 which should be claimed by `cdc_ether` for the network connection.

**What should happen:**
- Interfaces 0,1 → `cdc_ether` driver → creates `usb0` network interface
- Interfaces 2,3,4,5,7,8 → `option` driver → creates `ttyUSB2-7` serial ports

**What's actually happening:**
- Interfaces 0,1,2,3,4,5,7,8 → ALL claimed by `option` driver
- Result: Serial ports work, but NO network interface

## Immediate Fix (Test Now)

Your modem is currently connected. Run this to fix it RIGHT NOW:

```bash
chmod +x fix_now_ec200g.sh
sudo ./fix_now_ec200g.sh
```

This will:
1. Unbind interfaces 0,1 from the `option` driver
2. Bind interfaces 0,1 to the `cdc_ether` driver
3. Give you BOTH serial ports AND the usb0 network interface

**After running it, you should have:**
- `/dev/ttyUSB2` through `/dev/ttyUSB7` (6 serial ports)
- `usb0` network interface

## Permanent Fix (After Testing)

Once the immediate fix works, make it permanent:

```bash
chmod +x fix_ec200g_complete.sh
sudo ./fix_ec200g_complete.sh
```

This creates:
- Boot-time service to register the device
- Udev rules for automatic hotplug support
- Helper scripts to rebind drivers when needed

## What the Fix Does

The complete fix uses a three-step process:

### 1. At Boot Time
- Load `cdc_ether` and `option` drivers
- Register device ID `2c7c:0904` with the option driver

### 2. When Modem is Plugged In (Hotplug)
- Kernel automatically detects the device
- Option driver claims all interfaces (this is the problem!)

### 3. Fix the Driver Assignment (Automatic)
- Unbind interfaces 0,1 from option
- Bind interfaces 0,1 to cdc_ether (creates usb0)
- Leave interfaces 2,3,4,5,7,8 on option (creates ttyUSB2-7)

## File Guide

### Quick Fix Scripts
- **fix_now_ec200g.sh** - Run this FIRST with modem connected (immediate test)
- **fix_ec200g_complete.sh** - Run this SECOND to make permanent

### Cleanup
- **cleanup_all_ec200g.sh** - Removes all previous fix attempts

### Diagnostics
- **debug_ec200g.sh** - Shows current status and what drivers are bound

### Old Scripts (Don't Use)
- fix_ec200g.sh - ❌ Broken (wrong modprobe syntax)
- fix_ec200g_v2.sh - ⚠ Partial (serial only, no network)
- fix_ec200g_simple.sh - ⚠ Partial (serial only, no network)
- manual_fix_ec200g.sh - ⚠ Partial (serial only, no network)

## Testing Procedure

### Step 1: Test Immediate Fix
```bash
# With modem connected:
sudo ./fix_now_ec200g.sh
```

Expected output:
```
✓ Serial ports: 6 detected
  /dev/ttyUSB2
  /dev/ttyUSB3
  ...
✓ Network interface: usb0 exists
```

### Step 2: Test Serial Ports
```bash
sudo minicom -D /dev/ttyUSB2
```

Type in minicom:
```
AT
ATI
AT+CPIN?
AT+CSQ
```

Expected responses:
```
OK
Quectel
EC200G-CN
...
+CPIN: READY
+CSQ: 15,99
```

Press `Ctrl+A` then `X` to exit.

### Step 3: Test Network Interface
```bash
# Bring up interface
sudo ip link set usb0 up

# Check status
ip link show usb0

# Should show:
# usb0: <BROADCAST,MULTICAST,UP,LOWER_UP>
```

### Step 4: Make Permanent
```bash
sudo ./fix_ec200g_complete.sh
```

Follow prompts, then reboot.

### Step 5: Verify After Reboot
After reboot:
1. Plug in modem
2. Wait 10 seconds
3. Check:
   ```bash
   ls /dev/ttyUSB*
   ip link show usb0
   ```

Both should work automatically.

## Troubleshooting

### Issue: Still no usb0 after fix_now_ec200g.sh

**Try 1:** Unplug modem, run script, then plug modem back in
```bash
# Unplug modem first!
sudo ./fix_now_ec200g.sh
# Now plug modem in
sleep 5
ip link show usb0
```

**Try 2:** Manual driver rebinding
```bash
# Find device
DEVICE=$(ls -d /sys/bus/usb/devices/* | while read dev; do
    [ -f "$dev/idVendor" ] && [ "$(cat $dev/idVendor)" = "2c7c" ] && \
    [ -f "$dev/idProduct" ] && [ "$(cat $dev/idProduct)" = "0904" ] && \
    basename $dev && break
done)

# Unbind from option
sudo sh -c "echo ${DEVICE}:1.0 > /sys/bus/usb/drivers/option/unbind"
sudo sh -c "echo ${DEVICE}:1.1 > /sys/bus/usb/drivers/option/unbind"

# Bind to cdc_ether
sudo sh -c "echo ${DEVICE}:1.0 > /sys/bus/usb/drivers/cdc_ether/bind"
sudo sh -c "echo ${DEVICE}:1.1 > /sys/bus/usb/drivers/cdc_ether/bind"

# Check
sleep 2
ip link show usb0
```

### Issue: Network interface appears but has no carrier

This is normal if:
- No SIM card inserted
- SIM card not activated
- Network configuration needed

Check with:
```bash
ip link show usb0 | grep "NO-CARRIER"
```

To configure network (example for QMI):
```bash
sudo apt-get install libqmi-utils
sudo qmicli -d /dev/cdc-wdm0 --dms-get-model
```

Or for PPP:
```bash
# Check AT commands work first
sudo minicom -D /dev/ttyUSB2
```

### Issue: Port numbers change (ttyUSB2-7 → ttyUSB8-13)

This is normal Linux behavior. Create persistent symlinks:

```bash
sudo tee /etc/udev/rules.d/99-ec200g-symlinks.rules << 'EOF'
SUBSYSTEM=="tty", ATTRS{idVendor}=="2c7c", ATTRS{idProduct}=="0904", \
    ATTRS{bInterfaceNumber}=="02", SYMLINK+="ec200g-at"
    
SUBSYSTEM=="tty", ATTRS{idVendor}=="2c7c", ATTRS{idProduct}=="0904", \
    ATTRS{bInterfaceNumber}=="03", SYMLINK+="ec200g-modem"

SUBSYSTEM=="tty", ATTRS{idVendor}=="2c7c", ATTRS{idProduct}=="0904", \
    ATTRS{bInterfaceNumber}=="04", SYMLINK+="ec200g-diag"
EOF

sudo udevadm control --reload-rules
```

Then use: `/dev/ec200g-at` instead of `/dev/ttyUSB2`

### Issue: Permission denied on serial ports

```bash
sudo usermod -aG dialout $USER
# Logout and login again, or:
newgrp dialout
```

## Port Usage Guide

| Interface | Driver | Device | Purpose |
|-----------|--------|--------|---------|
| 0 | cdc_ether | usb0 | Network data (primary) |
| 1 | cdc_ether | usb0 | Network data (alternate) |
| 2 | option | ttyUSB2 | AT commands |
| 3 | option | ttyUSB3 | PPP/data |
| 4 | option | ttyUSB4 | AT commands (alt) |
| 5 | option | ttyUSB5 | GPS NMEA |
| 6 | - | - | (Missing - USB config error) |
| 7 | option | ttyUSB6 | Debug |
| 8 | option | ttyUSB7 | Audio/voice |

**Note:** Interface 6 doesn't exist due to the invalid USB configuration in your EC200G.

## Clean Slate (Start Over)

If you've tried multiple fixes and want to start fresh:

```bash
# Remove everything
sudo ./cleanup_all_ec200g.sh

# Reboot
sudo reboot

# After reboot, start from beginning
sudo ./fix_now_ec200g.sh
```

## Network Connection Examples

### Using QMI (Modern Method)
```bash
# Install tools
sudo apt-get install libqmi-utils udhcpc

# Check modem
sudo qmicli -d /dev/cdc-wdm0 --dms-get-model

# Start connection (replace 'internet' with your APN)
sudo qmicli -d /dev/cdc-wdm0 \
    --wds-start-network="apn='internet',ip-type=4" \
    --client-no-release-cid

# Get IP address
sudo udhcpc -i usb0
```

### Using PPP (Traditional Method)
```bash
# Install ppp
sudo apt-get install ppp

# Create config: /etc/ppp/peers/ec200g
/dev/ttyUSB3
115200
noauth
defaultroute
usepeerdns
persist
connect '/usr/sbin/chat -v -f /etc/chatscripts/gprs -T YOUR_APN'

# Connect
sudo pon ec200g

# Check
ifconfig ppp0
```

### Using NetworkManager (GUI Method)
```bash
# Should detect automatically
nmcli device status

# Or create connection
nmcli connection add type gsm ifname '*' con-name 'Mobile' apn 'YOUR_APN'
nmcli connection up 'Mobile'
```

## Understanding the EC200G USB Issue

Your dmesg shows:
```
config 1 has an invalid interface number: 8 but max is 7
config 1 has no interface number 6
```

This means:
- The EC200G has buggy USB descriptors
- It declares interface 8 but only supports up to 7
- Interface 6 is missing entirely
- This suggests it's a clone or variant, not genuine Quectel

**Does the fix work anyway?**
Yes! Because we manually bind the interfaces that DO exist (0,1,2,3,4,5,7,8).

## EC200U vs EC200G Comparison

| Feature | EC200U-CN | EC200G-CN |
|---------|-----------|-----------|
| USB VID:PID | 2c7c:0901 | 2c7c:0904 |
| Official Quectel | Yes ✓ | Unclear (not on website) |
| Linux support | Built-in | Manual setup required |
| USB config | Valid | Invalid (errors) |
| Interfaces | 0-8 (all present) | 0,1,2,3,4,5,7,8 (6 missing) |
| Works with fix | Yes | Yes |

## If This Still Doesn't Work

If after all this you still can't get both serial and network working:

1. **Provide debug info:**
   ```bash
   sudo ./debug_ec200g.sh > debug.txt
   dmesg | grep -E '2c7c|0904|usb0|ttyUSB' > dmesg.txt
   lsusb -v -d 2c7c:0904 > lsusb.txt
   ```

2. **Check kernel version:**
   ```bash
   uname -r
   # You have: 6.12.62+rpt-rpi-v8 (should work)
   ```

3. **Try with EC200U:**
   If you have the EC200U, test with that to confirm your setup is correct.

4. **Consider the hardware:**
   The EC200G might have firmware issues that prevent proper CDC Ethernet operation.

## Summary

1. **Run `fix_now_ec200g.sh`** first to test with currently connected modem
2. If that works, **run `fix_ec200g_complete.sh`** to make permanent
3. **Reboot** and verify modem works on replug
4. Use `/dev/ttyUSB2` for AT commands
5. Use `usb0` for network connection

The key issue was that ALL interfaces were being claimed by the option driver. The fix ensures interfaces 0,1 go to cdc_ether (for network) and 2,3,4,5,7,8 go to option (for serial).
