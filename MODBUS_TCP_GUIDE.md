# Modbus TCP Sensor Configuration Guide

## Overview

The datalogger now supports reading sensor values directly from Modbus TCP devices in addition to IQ Web Connect HTML parsing. This allows you to connect to PLCs, RTUs, and other Modbus-enabled devices.

## Configuration Fields

### Connection Settings

- **IP Address** (required): IP address of the Modbus device (e.g., `192.168.1.100`)
- **Port** (optional): TCP port number (default: `502`)
- **Slave ID** (required): Modbus slave/unit ID (1-247)

### Register Settings

- **Register Type** (required):
  - `Holding Register (FC3)`: Read/Write registers (function code 3)
  - `Input Register (FC4)`: Read-only registers (function code 4)
  - `Coil (FC1)`: Single-bit read/write (function code 1)
  - `Discrete Input (FC2)`: Single-bit read-only (function code 2)

- **Register Address** (required): Starting register address (0-65535)

### Data Type

Select the data type that matches how your device stores the value:

#### 16-bit Types (1 register):
- **uint16**: 16-bit unsigned integer (0 to 65535)
- **int16**: 16-bit signed integer (-32768 to 32767)
- **uint8_high**: High byte of register as unsigned (0-255)
- **uint8_low**: Low byte of register as unsigned (0-255)
- **int8_high**: High byte of register as signed (-128 to 127)
- **int8_low**: Low byte of register as signed (-128 to 127)

#### 32-bit Types (2 registers):
- **uint32**: 32-bit unsigned integer (0 to 4294967295)
- **int32**: 32-bit signed integer (-2147483648 to 2147483647)
- **float32**: 32-bit IEEE 754 floating point

### Byte/Word Order

For values spanning multiple bytes or registers, you need to specify the byte and word order:

#### Byte Order (within each 16-bit register):
- **Big Endian (AB)**: Most significant byte first (default, most common)
- **Little Endian (BA)**: Least significant byte first

#### Word Order (for 32-bit values across 2 registers):
- **Big Endian (ABCD)**: High word in first register (default, most common)
- **Little Endian (DCBA)**: Low word in first register

### Common Byte/Word Order Combinations:

| Order | Description | Registers | Byte Layout |
|-------|-------------|-----------|-------------|
| Big-Big (ABCD) | Standard Modbus | [High, Low] | Most common |
| Big-Little (CDAB) | Word swap | [Low, High] | Some PLCs |
| Little-Big (BADC) | Byte swap | [High, Low] | Rare |
| Little-Little (DCBA) | Fully reversed | [Low, High] | Very rare |

### ODAMS Fields

- **Parameter Name** (required): Name to send to ODAMS (e.g., `ph`, `temperature`, `flow`)
- **Unit** (required): Unit of measurement (e.g., `pH`, `°C`, `m3/h`)

## Configuration Examples

### Example 1: Temperature Sensor (16-bit signed)

```
IP Address: 192.168.1.50
Port: 502
Slave ID: 1
Register Type: Input Register (FC4)
Register Address: 100
Data Type: int16
Byte Order: Big Endian
Parameter Name: temperature
Unit: °C
```

This reads a signed 16-bit temperature value from input register 100.

### Example 2: Flow Meter (32-bit float)

```
IP Address: 192.168.1.51
Port: 502
Slave ID: 2
Register Type: Holding Register (FC3)
Register Address: 5000
Data Type: float32
Byte Order: Big Endian
Word Order: Big Endian
Parameter Name: flow
Unit: m3/h
```

This reads a 32-bit float flow value from holding registers 5000-5001.

### Example 3: pH Sensor (High byte of register)

```
IP Address: 192.168.1.52
Port: 502
Slave ID: 1
Register Type: Holding Register (FC3)
Register Address: 0
Data Type: uint8_high
Byte Order: Big Endian
Parameter Name: ph
Unit: pH
```

This reads only the high byte of register 0 as an unsigned 8-bit value.

### Example 4: Level Transmitter (32-bit unsigned, word-swapped)

```
IP Address: 192.168.1.53
Port: 502
Slave ID: 3
Register Type: Input Register (FC4)
Register Address: 200
Data Type: uint32
Byte Order: Big Endian
Word Order: Little Endian (CDAB)
Parameter Name: level
Unit: mm
```

This reads a 32-bit unsigned value with word order swapped.

## Testing Modbus Sensors

### 1. Web UI

1. Navigate to **Sensors** page
2. Click **Modbus TCP** tab
3. Click **+ Add Modbus Sensor**
4. Fill in the configuration fields
5. Click **Save Configuration**
6. Go to **Dashboard**
7. Click **Test Fetch** to verify connection

### 2. Using Python (Manual Test)

```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.1.100', port=502)
if client.connect():
    # Read holding register 0
    result = client.read_holding_registers(0, 1, slave=1)
    if not result.isError():
        print(f"Register value: {result.registers[0]}")
    client.close()
```

### 3. Using modpoll (Command Line)

```bash
# Read 1 holding register at address 0 from slave 1
modpoll -m tcp -a 1 -r 0 -c 1 192.168.1.100

# Read 2 registers (for 32-bit value)
modpoll -m tcp -a 1 -r 100 -c 2 192.168.1.100
```

## Troubleshooting

### Connection Issues

**Error**: "Failed to connect to Modbus device"
- Check IP address and port
- Verify device is powered on and network accessible
- Try ping: `ping 192.168.1.100`
- Verify firewall settings (port 502 must be open)

### No Data Received

**Error**: "Modbus read error"
- Verify slave ID is correct
- Check register address (some devices use 1-based addressing)
- Ensure register type matches device configuration
- Try reading with modpoll tool first

### Wrong Values

**Issue**: Values are incorrect or garbage
- Check data type (16-bit vs 32-bit)
- Try different byte/word order combinations
- Verify register contains the expected data type
- Check device documentation for register map

### Mixed Sensor Types

The datalogger can mix IQ Web Connect and Modbus TCP sensors:
```json
{
  "server_running": true,
  "sensors": [
    {
      "type": "iq_web_connect",
      "sensor_id": "S01",
      "param_name": "bod",
      "unit": "mg/L"
    },
    {
      "type": "modbus_tcp",
      "ip": "192.168.1.100",
      "slave_id": 1,
      "register_type": "holding",
      "register_address": 0,
      "data_type": "float32",
      "byte_order": "big",
      "word_order": "big",
      "param_name": "ph",
      "unit": "pH"
    }
  ]
}
```

## Device-Specific Notes

### Schneider Electric PLCs
- Typically use Big-Big (ABCD) byte order
- Holding registers usually start at 400001 (address 0)
- Input registers start at 300001 (address 0)

### Allen-Bradley/Rockwell PLCs
- May use Big-Little (CDAB) word order
- Check specific PLC model documentation

### Siemens PLCs
- S7-1200/1500 use Big-Big (ABCD) byte order
- S7-200 may vary, check documentation

### Custom Devices
- Always refer to device's Modbus register map
- Test with modpoll first to verify configuration

## Installation

Modbus TCP support requires the `pymodbus` library:

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install pymodbus==3.5.4
```

## Performance Considerations

- Each Modbus sensor adds ~50-200ms to fetch time (depending on network)
- For multiple sensors on same device, they are read sequentially
- Consider network latency when using DEV_MODE (1-minute intervals)
- Use Modbus/TCP (not Modbus RTU over TCP) for best performance

## Security

- Modbus TCP has no built-in authentication
- Use network segmentation (VLANs) to protect Modbus devices
- Consider using VPN for remote access
- Implement firewall rules to restrict access to port 502
