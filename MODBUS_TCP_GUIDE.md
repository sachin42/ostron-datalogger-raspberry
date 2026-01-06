# Modbus Sensor Configuration Guide

## Overview

The datalogger supports reading sensor values directly from Modbus devices via:
- **Modbus TCP** - Network-based communication over Ethernet
- **Modbus RTU** - Serial communication over RS485/RS232

This allows you to connect to PLCs, RTUs, and other Modbus-enabled devices in addition to IQ Web Connect HTML parsing.

## Modbus TCP Configuration

### Connection Settings

- **IP Address** (required): IP address of the Modbus device (e.g., `192.168.1.100`)
- **Port** (optional): TCP port number (default: `502`)
- **Slave ID** (required): Modbus slave/unit ID (1-247)

## Modbus RTU (RS485) Configuration

### Serial Device Configuration

Configure the RS485/serial port (only one serial device supported):

- **Serial Port** (required): Port name
  - Windows: `COM1`, `COM7`, etc.
  - Linux: `/dev/ttyUSB0`, `/dev/ttyS0`, etc.
- **Baud Rate** (required): Communication speed (default: `9600`)
  - Common values: 9600, 19200, 38400, 57600, 115200
- **Parity** (optional): Error checking (default: `N`)
  - `N`: None (most common)
  - `E`: Even
  - `O`: Odd
- **Data Bits** (optional): Number of data bits (default: `8`)
  - Values: 7 or 8
- **Stop Bits** (optional): Number of stop bits (default: `1`)
  - Values: 1 or 2
- **Timeout** (optional): Communication timeout in seconds (default: `3`)
  - Range: 1-10 seconds

### RTU Sensors

After configuring the serial device, add sensors with different slave IDs on the same RS485 bus:

- **Slave ID** (required): Modbus slave/unit ID (1-247) - Each sensor must have a unique slave ID

## Common Configuration Fields

The following fields apply to both Modbus TCP and Modbus RTU sensors:

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

For 32-bit values (int32, uint32, float32), you need to specify how bytes are arranged across the two 16-bit registers:

#### Understanding Byte Order Settings

**Byte Order** - Controls byte arrangement within each 16-bit register:
- **Big Endian (AB)**: Most significant byte first (standard)
- **Little Endian (BA)**: Least significant byte first (byte swap)

**Word Order** - Controls which register contains the high/low word:
- **Big Endian**: First register is high word (most significant)
- **Little Endian**: First register is low word (least significant)

### Byte/Word Order Combinations for 32-bit Values:

| Byte Order | Word Order | Result | Common Name | Usage |
|------------|------------|--------|-------------|-------|
| Big | Big | ABCD | Big Endian | Standard Modbus (most common) |
| Little | Little | DCBA | Little Endian | Fully reversed (rare) |
| Little | Big | BADC | Big Endian with Byte Swap | Some PLCs |
| Big | Little | CDAB | Little Endian with Byte Swap | Some PLCs |

**Note**: If your Modbus device documentation or configuration tool shows:
- "Big Endian" → Use Byte Order: Big, Word Order: Big (ABCD)
- "Little Endian" → Use Byte Order: Little, Word Order: Little (DCBA)
- "Big Endian with Byte Swap" → Use Byte Order: Little, Word Order: Big (BADC)
- "Little Endian with Byte Swap" → Use Byte Order: Big, Word Order: Little (CDAB)

### ODAMS Fields

- **Parameter Name** (required): Name to send to ODAMS (e.g., `ph`, `temperature`, `flow`)
- **Unit** (required): Unit of measurement (e.g., `pH`, `°C`, `m3/h`)

## Configuration Examples

### Modbus TCP Examples

#### Example 1: Temperature Sensor (16-bit signed)

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

#### Example 2: Flow Meter (32-bit float)

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

#### Example 3: pH Sensor (High byte of register)

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

#### Example 4: Level Transmitter (32-bit unsigned, word-swapped)

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

### Modbus RTU Examples

#### Serial Device Configuration Example

```
Serial Port: COM7 (Windows) or /dev/ttyUSB0 (Linux)
Baud Rate: 9600
Parity: None (N)
Data Bits: 8
Stop Bits: 1
Timeout: 3 seconds
```

#### Example 1: Multiple Temperature Sensors on RS485 Bus

**Serial Device:** COM7, 9600 baud, 8N1

**Sensor 1 - Warehouse Temperature:**
```
Slave ID: 1
Register Type: Input Register (FC4)
Register Address: 0
Data Type: int16
Byte Order: Big Endian
Parameter Name: temp_warehouse
Unit: °C
```

**Sensor 2 - Cold Storage Temperature:**
```
Slave ID: 2
Register Type: Input Register (FC4)
Register Address: 0
Data Type: int16
Byte Order: Big Endian
Parameter Name: temp_cold_storage
Unit: °C
```

**Sensor 3 - Outdoor Temperature:**
```
Slave ID: 3
Register Type: Input Register (FC4)
Register Address: 0
Data Type: int16
Byte Order: Big Endian
Parameter Name: temp_outdoor
Unit: °C
```

This configuration reads from 3 different temperature sensors on the same RS485 bus, each with a unique slave ID.

#### Example 2: Flow Meter on RS485 (32-bit float)

**Serial Device:** /dev/ttyUSB0, 19200 baud, 8N1

**Flow Sensor:**
```
Slave ID: 1
Register Type: Holding Register (FC3)
Register Address: 100
Data Type: float32
Byte Order: Big Endian
Word Order: Big Endian
Parameter Name: flow_rate
Unit: m3/h
```

This reads a 32-bit float value from an RS485 flow meter.

#### Example 3: Mixed Sensors on RS485 Bus

**Serial Device:** COM3, 9600 baud, Even parity, 8E1

**pH Meter:**
```
Slave ID: 10
Register Type: Holding Register (FC3)
Register Address: 0
Data Type: uint16
Byte Order: Big Endian
Parameter Name: ph
Unit: pH
```

**Conductivity Meter:**
```
Slave ID: 11
Register Type: Holding Register (FC3)
Register Address: 5
Data Type: uint32
Byte Order: Big Endian
Word Order: Big Endian
Parameter Name: conductivity
Unit: μS/cm
```

**Turbidity Meter:**
```
Slave ID: 12
Register Type: Input Register (FC4)
Register Address: 20
Data Type: float32
Byte Order: Big Endian
Word Order: Big Endian
Parameter Name: turbidity
Unit: NTU
```

This shows different sensor types (pH, conductivity, turbidity) on the same RS485 bus with different slave IDs.

## Testing Modbus Sensors

### 1. Web UI Testing

#### Testing Modbus TCP:
1. Navigate to **Sensors** page
2. Click **Modbus TCP** tab
3. Click **+ Add Modbus Sensor**
4. Fill in the configuration fields (IP, Slave ID, Register settings, etc.)
5. Click **Save Configuration**
6. Go to **Dashboard** to see real-time values
7. Click **Test Fetch** to manually trigger data fetch

#### Testing Modbus RTU:
1. Navigate to **Sensors** page
2. Click **Modbus RTU (RS485)** tab
3. Configure the serial device (Port, Baud Rate, Parity, etc.)
4. Click **+ Add RTU Sensor** for each sensor on the bus
5. Fill in sensor configuration (Slave ID, Register settings, etc.)
6. Click **Save Configuration**
7. Go to **Dashboard** to see real-time values
8. Click **Test Fetch** to manually trigger data fetch

**Important:** For RTU sensors, ensure:
- Serial port has correct permissions (Linux: `sudo chmod 666 /dev/ttyUSB0`)
- No other applications are using the serial port
- RS485 adapter is properly connected
- Each sensor has a unique slave ID

### 2. Using Python (Manual Test)

#### Modbus TCP Test

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

#### Modbus RTU Test

```python
from pymodbus.client import ModbusSerialClient

client = ModbusSerialClient(
    port='COM7',  # or '/dev/ttyUSB0' on Linux
    baudrate=9600,
    parity='N',
    stopbits=1,
    bytesize=8,
    timeout=3
)

if client.connect():
    # Read holding register 0 from slave 1
    result = client.read_holding_registers(0, 1, slave=1)
    if not result.isError():
        print(f"Register value: {result.registers[0]}")
    client.close()
```

### 3. Using modpoll (Command Line)

#### Modbus TCP

```bash
# Read 1 holding register at address 0 from slave 1
modpoll -m tcp -a 1 -r 0 -c 1 192.168.1.100

# Read 2 registers (for 32-bit value)
modpoll -m tcp -a 1 -r 100 -c 2 192.168.1.100
```

#### Modbus RTU

```bash
# Read 1 holding register at address 0 from slave 1 on COM7
modpoll -m rtu -b 9600 -p none -a 1 -r 0 -c 1 COM7

# Read 2 registers (for 32-bit value) on Linux
modpoll -m rtu -b 9600 -p none -a 1 -r 100 -c 2 /dev/ttyUSB0

# With even parity
modpoll -m rtu -b 9600 -p even -a 1 -r 0 -c 1 COM7
```

## Troubleshooting

### Modbus TCP Issues

#### Connection Issues

**Error**: "Failed to connect to Modbus device"

- Check IP address and port
- Verify device is powered on and network accessible
- Try ping: `ping 192.168.1.100`
- Verify firewall settings (port 502 must be open)
- Check if device supports Modbus TCP (some only support RTU)

#### No Data Received

**Error**: "Modbus read error"

- Verify slave ID is correct
- Check register address (some devices use 1-based addressing)
- Ensure register type matches device configuration
- Try reading with modpoll tool first
- Check device Modbus settings (enabled, correct port)

#### Wrong Values

**Issue**: Values are incorrect or garbage

- Check data type (16-bit vs 32-bit)
- Try different byte/word order combinations
- Verify register contains the expected data type
- Check device documentation for register map

### Modbus RTU Issues

#### Serial Port Connection Issues

**Error**: "Failed to connect to Modbus RTU device"

- **Port not found**: Verify COM port or /dev/ttyUSB device exists
  - Windows: Check Device Manager → Ports (COM & LPT)
  - Linux: Run `ls /dev/tty*` to list available ports
- **Permission denied** (Linux): Grant access to serial port
  - `sudo chmod 666 /dev/ttyUSB0` (temporary)
  - `sudo usermod -a -G dialout $USER` (permanent, logout required)
- **Port in use**: Close other applications using the port
  - Check if another Modbus client/scanner is running
  - Check if serial terminal (putty, minicom) is open
- **USB adapter not detected**: Check USB cable and adapter
  - Try different USB port
  - Check adapter LED indicators
  - Verify driver installation (CH340, FTDI, etc.)

#### Communication Settings Mismatch

**Error**: "Modbus RTU read error" or timeout

- **Baud rate mismatch**: Verify device baud rate
  - Common: 9600, 19200, 38400
  - Check device DIP switches or configuration menu
- **Parity mismatch**: Check device parity setting
  - Most common: None (N)
  - Some devices use Even (E)
- **Stop bits/Data bits**: Usually 8N1 (8 data, no parity, 1 stop)
- **Timeout too short**: Increase timeout if bus is long or slow
  - Default: 3 seconds
  - Long cables or many devices: Try 5-10 seconds

#### RTU-Specific Issues

**Issue**: Some sensors work, others don't

- Check slave IDs are unique and correct
- Verify all sensors are powered and on the bus
- Check RS485 termination resistors (120Ω on both ends)
- Check RS485 wiring polarity (A/B or +/-)

**Issue**: Intermittent communication errors

- Check RS485 cable length (max 1200m without repeater)
- Check for electromagnetic interference (EMI)
- Verify proper grounding
- Add or check termination resistors
- Reduce baud rate for longer cables

**Issue**: No response from any sensor

- Verify RS485 adapter TX/RX LEDs blink during communication
- Check RS485 wiring (A to A, B to B, not swapped)
- Try manually setting slave ID on one sensor and testing
- Use modpoll tool to verify basic connectivity

#### Wrong Values on RTU

Same as Modbus TCP, plus:

- **Cable issues**: Check RS485 cable quality and connections
- **Noise on bus**: Add shielded cable or twisted pair
- **Bus loading**: Too many devices can cause signal degradation
  - Max 32 devices per segment without repeater

### Mixed Sensor Types

The datalogger can mix IQ Web Connect, Modbus TCP, and Modbus RTU sensors:

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
    },
    {
      "type": "modbus_rtu",
      "slave_id": 2,
      "register_type": "input",
      "register_address": 100,
      "data_type": "int16",
      "byte_order": "big",
      "param_name": "temperature",
      "unit": "°C"
    },
    {
      "type": "modbus_rtu",
      "slave_id": 3,
      "register_type": "holding",
      "register_address": 5000,
      "data_type": "float32",
      "byte_order": "big",
      "word_order": "big",
      "param_name": "flow_rate",
      "unit": "m3/h"
    }
  ],
  "rtu_device": {
    "port": "COM7",
    "baudrate": 9600,
    "parity": "N",
    "bytesize": 8,
    "stopbits": 1,
    "timeout": 3
  }
}
```

**Note:** All RTU sensors share the same serial device configuration but have unique slave IDs.

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
