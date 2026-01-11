# Analog Sensor Integration Guide

## Overview

The main datalogger can now fetch sensor data from the Waveshare analog acquisition server and send it to CPCB/ODAMS along with other sensors.

## Architecture

```
[4-20mA Sensors] → [Waveshare Module] → [Analog Server] → [Datalogger] → [CPCB/ODAMS]
                                        (Device 1)       (Device 2)
                                        Port 8000        Port 9999
```

## Setup Instructions

### Step 1: Configure Analog Server

1. **Run analog server on separate device** (Raspberry Pi, PC, etc.):
   ```bash
   python analogserver.py
   ```
   Server starts on port 8000

2. **Configure channels via web UI** (http://device-ip:8000):
   - Go to "Configuration" tab
   - For each channel:
     - Enable channel
     - Set channel name (e.g., "Flow Rate")
     - Set min value at 4mA (e.g., 0)
     - Set max value at 20mA (e.g., 150)
     - Set unit (e.g., m³/hr)
     - Set decimal places

3. **Configure device settings**:
   - Go to "Device Settings" tab
   - Set serial port (COM7 or /dev/ttyUSB0)
   - Configure baudrate, parity, etc.
   - Save and verify device connects

4. **Monitor data** in "Monitor" tab to verify readings

### Step 2: Configure Datalogger

1. **Access datalogger web UI** (http://localhost:9999)

2. **Go to Sensors page** and select "Analog" tab

3. **Add analog sensor**:
   - Server URL: `http://192.168.1.100:8000` (analog server IP)
   - Channel ID: Select channel (1-8)
   - Parameter Name: CPCB parameter name (e.g., "flow", "temperature")
   - Unit: Unit for this parameter (e.g., "m³/hr", "°C") - should match analog server

4. **Save configuration**

5. **Verify on Dashboard**:
   - Check sensor shows "Analog (4-20mA)" badge
   - Verify value updates

## Configuration Example

### Scenario: Flow Meter

**Analog Server Configuration (http://192.168.1.100:8000):**
```
Channel 1:
- Enabled: ✓
- Name: "Flow Rate"
- Min Value: 0 (at 4mA)
- Max Value: 150 (at 20mA)
- Unit: m³/hr
- Decimals: 2
```

**Datalogger Configuration:**
```json
{
  "type": "analog",
  "server_url": "http://192.168.1.100:8000",
  "channel_id": 1,
  "param_name": "flow",
  "unit": "m³/hr"
}
```

**Result:**
- Analog server reads 12.5mA → Calculates 79.69 m³/hr
- Datalogger fetches value via API
- Sends to CPCB as: `{"parameter": "flow", "value": "79.69", "unit": "m³/hr"}`

## Network Configuration

### Same Device (Testing)

If running both servers on same machine:
```
Server URL: http://localhost:8000
```

### Different Devices (Production)

1. **Find analog server IP**:
   ```bash
   # On Linux/Raspberry Pi
   hostname -I

   # On Windows
   ipconfig
   ```

2. **Use in datalogger**:
   ```
   Server URL: http://192.168.1.100:8000
   ```

3. **Ensure network connectivity**:
   ```bash
   # Test from datalogger machine
   curl http://192.168.1.100:8000/api/status
   ```

### Firewall Rules

Ensure port 8000 is open on analog server device:

```bash
# Linux/Raspberry Pi
sudo ufw allow 8000

# Windows
# Add inbound rule for port 8000 in Windows Firewall
```

## Multiple Analog Servers

You can configure sensors from multiple analog servers:

```json
[
  {
    "type": "analog",
    "server_url": "http://192.168.1.100:8000",
    "channel_id": 1,
    "param_name": "flow",
    "unit": "m³/hr"
  },
  {
    "type": "analog",
    "server_url": "http://192.168.1.101:8000",
    "channel_id": 2,
    "param_name": "pressure",
    "unit": "bar"
  }
]
```

Datalogger will fetch from each server efficiently (one API call per server).

## Mixing Sensor Types

The datalogger supports all sensor types simultaneously:

```json
{
  "sensors": [
    {
      "type": "iq_web_connect",
      "sensor_id": "S01",
      "param_name": "ph",
      "unit": "pH"
    },
    {
      "type": "modbus_tcp",
      "ip": "192.168.1.50",
      "slave_id": 1,
      "param_name": "temperature",
      "unit": "°C"
    },
    {
      "type": "modbus_rtu",
      "slave_id": 2,
      "param_name": "pressure",
      "unit": "bar"
    },
    {
      "type": "analog",
      "server_url": "http://192.168.1.100:8000",
      "channel_id": 1,
      "param_name": "flow",
      "unit": "m³/hr"
    }
  ]
}
```

All sensors are fetched, averaged, and sent to CPCB together.

## Data Flow

### 1. Data Collection (Every 10-30 seconds)

```python
# Fetch from analog server
GET http://192.168.1.100:8000/api/channels

# Response:
{
  "channels": {
    "1": {
      "value": 79.69,
      "unit": "m³/hr",
      "enabled": true
    }
  }
}

# Store for averaging
```

### 2. Data Averaging (1-15 minutes)

- Collects multiple samples
- Calculates average
- Rounds to configured decimals

### 3. Data Transmission

```json
{
  "data": [{
    "stationId": "station_8203",
    "device_data": [{
      "deviceId": "device_7025",
      "params": [
        {
          "parameter": "flow",
          "value": "79.69",
          "unit": "m³/hr",
          "timestamp": 1736423400000,
          "flag": "U"
        }
      ]
    }]
  }]
}
```

Encrypted and sent to CPCB/ODAMS.

## Troubleshooting

### Analog Server Not Reachable

**Symptom:** Datalogger logs show "Network error fetching from analog server"

**Solutions:**
1. Verify analog server is running: `http://192.168.1.100:8000`
2. Check network connectivity: `ping 192.168.1.100`
3. Test API manually: `curl http://192.168.1.100:8000/api/status`
4. Check firewall allows port 8000

### Channel Not Enabled

**Symptom:** Log shows "Analog channel X not enabled or not found"

**Solutions:**
1. Open analog server web UI
2. Go to "Configuration" tab
3. Enable the channel
4. Save configuration

### Device Not Connected

**Symptom:** Analog server shows "device_connected": false

**Solutions:**
1. Check serial port configuration in analog server
2. Verify Waveshare module is powered
3. Check RS485 wiring (A to A, B to B)
4. Verify correct COM port / /dev/ttyUSB0

### Wrong Values

**Symptom:** Values don't match expected range

**Solutions:**
1. Verify 4-20mA sensor wiring
2. Check scaling configuration in analog server
3. Confirm min/max values match sensor specifications
4. Test with known current source (multimeter)

### No Data on Dashboard

**Symptom:** Analog sensor shows "--" on datalogger dashboard

**Solutions:**
1. Check datalogger logs for fetch errors
2. Verify param_name matches between systems
3. Ensure channel is enabled in analog server
4. Check server_running is true in datalogger

## API Reference

### Analog Server Endpoints

#### GET /api/channels
Get all channel data.

**Response:**
```json
{
  "timestamp": "2026-01-11T14:30:00",
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
    }
  },
  "device_connected": true
}
```

#### GET /api/channel/<id>
Get specific channel data.

#### GET /api/status
Get server status.

**Response:**
```json
{
  "server_running": true,
  "device_connected": true,
  "device_port": "COM7",
  "read_interval": 2,
  "last_update": "2026-01-11T14:30:00"
}
```

## Performance Considerations

### Network Latency

- Analog server API typically responds in < 10ms
- Local network: minimal impact
- Remote network: may increase fetch time

### Update Frequency

- Analog server: reads device every 2 seconds (configurable)
- Datalogger: fetches every 10-30 seconds (based on DEV_MODE)
- CPCB transmission: 1-15 minutes (based on DEV_MODE)

### Resource Usage

- Analog server: ~50MB RAM, <1% CPU
- Datalogger fetch: ~100ms per server
- Network bandwidth: ~1KB per fetch

## Production Deployment

### Recommended Setup

1. **Analog Server:**
   - Raspberry Pi 4 or equivalent
   - Connected to Waveshare module via USB-RS485
   - Static IP address
   - Systemd service for auto-start

2. **Datalogger:**
   - Same or different device
   - Configure analog sensors with server IP
   - Monitor connectivity in logs

### High Availability

For critical applications:

1. **Run multiple analog servers** for redundancy
2. **Configure backup channels** on different servers
3. **Monitor device_connected status** in both systems
4. **Set up alerts** for connection failures

### Security

- Analog server has no authentication (local network only)
- Use firewall to restrict access to trusted devices
- Consider VPN for remote access
- No sensitive data transmitted (only sensor readings)

## Benefits of This Architecture

✅ **Flexible:** Analog server runs anywhere on network
✅ **Scalable:** Multiple dataloggers can read from one analog server
✅ **Maintainable:** Update analog server without touching datalogger
✅ **Testable:** Test analog acquisition separately from CPCB transmission
✅ **Reliable:** Independent failure domains (analog vs transmission)
✅ **User-Friendly:** Configure scaling visually in analog server UI

## Complete Example

### Equipment
- 1x Waveshare Modbus RTU Analog Input 8CH module
- 1x Flow meter with 4-20mA output (0-150 m³/hr)
- 1x Raspberry Pi (analog server)
- 1x PC/Raspberry Pi (datalogger)

### Setup
1. Connect flow meter 4-20mA output to Waveshare Channel 1
2. Connect Waveshare to Pi via USB-RS485
3. Run analog server on Pi, configure Channel 1 (0-150 m³/hr)
4. Configure datalogger to fetch from Pi IP, Channel 1
5. Verify on dashboard, then enable server_running
6. Data flows to CPCB/ODAMS automatically!

## Support

For analog server issues, see [ANALOG_SERVER_GUIDE.md](ANALOG_SERVER_GUIDE.md)

For datalogger issues, see [CLAUDE.md](CLAUDE.md) and [README.md](README.md)
