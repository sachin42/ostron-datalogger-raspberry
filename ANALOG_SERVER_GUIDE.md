# Waveshare Analog Acquisition Server Guide

## Overview

This server reads 4-20mA analog inputs from the Waveshare Modbus RTU Analog Input 8CH module and provides:
- REST API endpoints for each channel
- Web interface for configuration and monitoring
- Linear scaling from 4-20mA to engineering units (e.g., 0-150 m³/hr)

## Quick Start

### 1. Install Dependencies

The server uses the same dependencies as the main datalogger (already in requirements.txt):
- Flask
- pymodbus
- pyserial

### 2. Run the Server

```bash
python analogserver.py
```

The server will start on port 8000:
- **Web UI**: http://localhost:8000
- **API**: http://localhost:8000/api/

### 3. Configure Device

On first run, the server creates `analog_config.json` with default settings:

**Default Serial Settings:**
- Port: `COM7` (Windows) or `/dev/ttyUSB0` (Linux)
- Baudrate: 9600
- Parity: None
- Slave ID: 1
- Read Interval: 2 seconds

**To change device settings:**
1. Open http://localhost:8000
2. Go to "Device Settings" tab
3. Configure your serial port and parameters
4. Save and restart the server

## Web Interface

### 📈 Monitor Tab

Shows real-time data for all channels:
- Channel name and ID
- Current scaled value with unit
- Raw 4-20mA reading
- Enabled/disabled status
- Min/max range

**Example Display:**
```
Channel 1: Flow Rate
45.67 m³/hr
Raw: 12.5 mA (12500 µA)
Range: 0 - 150 m³/hr
```

### ⚙️ Configuration Tab

Configure each channel's scaling and parameters:

| Setting | Description | Example |
|---------|-------------|---------|
| **Enabled** | Enable/disable channel | ✓ Checked |
| **Channel Name** | Descriptive name | "Flow Rate" |
| **Min Value** | Value at 4mA | 0 |
| **Max Value** | Value at 20mA | 150 |
| **Unit** | Engineering unit | m³/hr |
| **Decimals** | Decimal places | 2 |

**Scaling Formula:**
```
value = ((current_ma - 4) / 16) * (max - min) + min
```

**Example Configuration:**
- **Sensor**: Flow meter outputting 4-20mA for 0-150 m³/hr
- **Min Value**: 0 (at 4mA = 0 m³/hr)
- **Max Value**: 150 (at 20mA = 150 m³/hr)
- **Reading**: 12mA → Scaled value = 75 m³/hr

### 🔧 Device Settings Tab

Configure serial port and Modbus parameters:
- **Port**: COM port (Windows) or /dev/ttyUSB0 (Linux)
- **Baudrate**: 9600, 19200, 38400, 57600, 115200
- **Parity**: None, Even, Odd
- **Slave ID**: Modbus slave address (1-247)
- **Read Interval**: How often to read data (seconds)

## REST API Endpoints

### GET /api/channels

Get data from all channels.

**Response:**
```json
{
  "timestamp": "2026-01-11T14:30:00.123456",
  "channels": {
    "1": {
      "id": 1,
      "name": "Flow Rate",
      "enabled": true,
      "raw_ua": 12500,
      "raw_ma": 12.5,
      "value": 79.69,
      "unit": "m³/hr",
      "min_range": 0,
      "max_range": 150
    },
    "2": { ... }
  },
  "device_connected": true
}
```

### GET /api/channel/<id>

Get data from specific channel (1-8).

**Example:** `GET /api/channel/1`

**Response:**
```json
{
  "timestamp": "2026-01-11T14:30:00.123456",
  "channel": {
    "id": 1,
    "name": "Flow Rate",
    "enabled": true,
    "raw_ua": 12500,
    "raw_ma": 12.5,
    "value": 79.69,
    "unit": "m³/hr",
    "min_range": 0,
    "max_range": 150
  },
  "device_connected": true
}
```

### GET /api/config

Get current configuration.

**Response:**
```json
{
  "device": {
    "port": "COM7",
    "baudrate": 9600,
    "parity": "N",
    "stopbits": 1,
    "bytesize": 8,
    "timeout": 1,
    "slave_id": 1
  },
  "channels": [
    {
      "id": 1,
      "name": "Channel 1",
      "enabled": true,
      "min_value": 0,
      "max_value": 100,
      "unit": "m³/hr",
      "decimals": 2
    }
  ],
  "read_interval": 2
}
```

### POST /api/config

Save configuration.

**Request Body:** Same format as GET /api/config response

**Response:**
```json
{
  "status": "success",
  "message": "Configuration saved"
}
```

### GET /api/status

Get server and device status.

**Response:**
```json
{
  "server_running": true,
  "device_connected": true,
  "device_port": "COM7",
  "read_interval": 2,
  "last_update": "2026-01-11T14:30:00.123456"
}
```

## Integration Examples

### Python Script

```python
import requests

# Get all channels
response = requests.get('http://localhost:8000/api/channels')
data = response.json()

for ch_id, channel in data['channels'].items():
    if channel['enabled']:
        print(f"{channel['name']}: {channel['value']} {channel['unit']}")

# Get specific channel
response = requests.get('http://localhost:8000/api/channel/1')
channel = response.json()['channel']
print(f"Flow rate: {channel['value']} {channel['unit']}")
```

### JavaScript/Node.js

```javascript
// Get all channels
fetch('http://localhost:8000/api/channels')
  .then(r => r.json())
  .then(data => {
    Object.values(data.channels).forEach(ch => {
      if (ch.enabled) {
        console.log(`${ch.name}: ${ch.value} ${ch.unit}`);
      }
    });
  });
```

### cURL

```bash
# Get all channels
curl http://localhost:8000/api/channels

# Get channel 1
curl http://localhost:8000/api/channel/1

# Get status
curl http://localhost:8000/api/status
```

## Configuration File

The server stores configuration in `analog_config.json`:

```json
{
  "device": {
    "port": "COM7",
    "baudrate": 9600,
    "parity": "N",
    "stopbits": 1,
    "bytesize": 8,
    "timeout": 1,
    "slave_id": 1
  },
  "channels": [
    {
      "id": 1,
      "name": "Flow Rate",
      "enabled": true,
      "min_value": 0,
      "max_value": 150,
      "unit": "m³/hr",
      "decimals": 2
    }
  ],
  "read_interval": 2
}
```

## Common Scaling Examples

### Flow Meter (0-150 m³/hr)
- Min Value: 0
- Max Value: 150
- Unit: m³/hr
- 4mA = 0 m³/hr
- 20mA = 150 m³/hr

### Pressure Transmitter (0-10 bar)
- Min Value: 0
- Max Value: 10
- Unit: bar
- 4mA = 0 bar
- 20mA = 10 bar

### Temperature Sensor (0-100°C)
- Min Value: 0
- Max Value: 100
- Unit: °C
- 4mA = 0°C
- 20mA = 100°C

### Level Sensor (0-5 meters)
- Min Value: 0
- Max Value: 5
- Unit: m
- 4mA = 0 m
- 20mA = 5 m

### pH Sensor (0-14 pH)
- Min Value: 0
- Max Value: 14
- Unit: pH
- 4mA = 0 pH
- 20mA = 14 pH

## Troubleshooting

### Device Not Connecting

**Check serial port permissions (Linux):**
```bash
sudo chmod 666 /dev/ttyUSB0
# or
sudo usermod -a -G dialout $USER
```

**Verify port name:**
- Windows: Device Manager → Ports (COM & LPT)
- Linux: `ls /dev/ttyUSB*` or `dmesg | grep tty`

**Check wiring:**
- RS485 A to A
- RS485 B to B
- Ground connection
- Power supply (12-24V DC)

### Reading Shows --

- Check if channel is enabled in configuration
- Verify Modbus slave ID matches device setting
- Check baudrate and parity settings
- Ensure device is powered and wired correctly

### Values Out of Range

The server automatically clamps values to 4-20mA range. If you see consistent 4mA or 20mA:
- Check sensor wiring and power
- Verify sensor is working properly
- Check if sensor is configured for 4-20mA output

## Device Register Information

| Register | Address | Function | Description |
|----------|---------|----------|-------------|
| Input Registers | 0x0000-0x0007 | Read (04) | Channel 1-8 values (µA) |
| Holding Registers | 0x1000-0x1007 | Read/Write (03/06) | Channel data types |
| Holding Register | 0x2000 | Read/Write (03/06) | UART parameters |
| Holding Register | 0x4000 | Read/Write (03/06) | Device address |

**Data Type Values (Register 0x1000-0x1007):**
- 0x0000: 0-5V
- 0x0001: 1-5V
- 0x0002: 0-20mA
- 0x0003: 4-20mA (default for standard version)
- 0x0004: Raw scale (0-4096)

## Running on Raspberry Pi

### Installation
```bash
# Install dependencies
pip3 install flask pymodbus pyserial

# Give serial port permissions
sudo usermod -a -G dialout pi

# Run server
python3 analogserver.py
```

### Run as Service (systemd)

Create `/etc/systemd/system/analogserver.service`:

```ini
[Unit]
Description=Analog Acquisition Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/dataloggerOstron
ExecStart=/usr/bin/python3 /home/pi/dataloggerOstron/analogserver.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable analogserver
sudo systemctl start analogserver
sudo systemctl status analogserver

# View logs
sudo journalctl -u analogserver -f
```

## Port Configuration

The server runs on port **8000** by default. To change:

Edit `analogserver.py` line near the bottom:
```python
app.run(host='0.0.0.0', port=8000, debug=False)
```

Change `8000` to your desired port.

## Security Notes

- The server listens on all interfaces (0.0.0.0) for easy access
- For production, consider adding authentication
- Use firewall rules to restrict access if exposed to network
- Configuration file contains no sensitive data (passwords, keys)

## Performance

- **Read Interval**: Default 2 seconds, adjustable 1-60 seconds
- **API Response**: < 10ms (data from memory)
- **Modbus Read**: ~100-200ms per read cycle
- **Concurrent Requests**: Supported (thread-safe)

## Support

For Waveshare device documentation:
https://www.waveshare.com/wiki/Modbus_RTU_Analog_Input_8CH

For issues with the server:
- Check `analog_config.json` for configuration errors
- Review console output for error messages
- Verify device is responding using Modbus test tools
