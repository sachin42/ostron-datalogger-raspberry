"""
Modbus TCP data fetcher with support for various data types and byte orders
"""
import struct
from typing import Optional, Dict, Any
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .constants import logger


# Register type mappings
REGISTER_TYPES = {
    'holding': 3,      # Function code 3: Read Holding Registers
    'input': 4,        # Function code 4: Read Input Registers    'coil': 1,         # Function code 1: Read Coils
    'discrete': 2      # Function code 2: Read Discrete Inputs
}


def read_modbus_value(
    ip: str,
    port: int,
    slave_id: int,
    register_type: str,
    register_address: int,
    data_type: str,
    byte_order: str = 'big',
    word_order: str = 'big'
) -> Optional[float]:
    """
    Read a value from Modbus TCP device

    Args:
        ip: IP address of the Modbus TCP device
        port: TCP port (usually 502)
        slave_id: Slave ID/Unit ID (1-247)
        register_type: Type of register ('holding', 'input', 'coil', 'discrete')
        register_address: Register address to read        data_type: Data type to read ('int16', 'uint16', 'int32', 'uint32', 'float32', 'int8_high', 'int8_low', 'uint8_high', 'uint8_low')
        byte_order: Byte order for multi-byte values ('big' or 'little')
        word_order: Word order for multi-register values ('big' or 'little')

    Returns:
        Parsed value as float, or None if error
    """
    try:
        client = ModbusTcpClient(ip, port=port, timeout=5)
        if not client.connect():
            logger.error(f"Failed to connect to Modbus device at {ip}:{port}")
            return None

        try:
            # Calculate register count based on data type
            if data_type in ['int16', 'uint16', 'int8_high', 'int8_low', 'uint8_high', 'uint8_low']:
                register_count = 1
            elif data_type in ['int32', 'uint32', 'float32']:
                register_count = 2
            else:
                logger.error(f"Unsupported data type: {data_type}")
                return None

            # Read registers based on type
            if register_type == 'holding':
                result = client.read_holding_registers(register_address, register_count, slave=slave_id)
            elif register_type == 'input':
                result = client.read_input_registers(register_address, register_count, slave=slave_id)
            elif register_type == 'coil':
                result = client.read_coils(register_address, 1, slave=slave_id)
                if not result.isError():
                    return float(result.bits[0])
                else:
                    logger.error(f"Modbus read error: {result}")
                    return None
            elif register_type == 'discrete':
                result = client.read_discrete_inputs(register_address, 1, slave=slave_id)
                if not result.isError():
                    return float(result.bits[0])
                else:
                    logger.error(f"Modbus read error: {result}")
                    return None
            else:
                logger.error(f"Unsupported register type: {register_type}")
                return None

            if result.isError():
                logger.error(f"Modbus read error: {result}")
                return None

            registers = result.registers

            # Parse the value based on data type
            value = parse_modbus_registers(registers, data_type, byte_order, word_order)

            logger.debug(f"Modbus read from {ip}:{port} slave {slave_id} reg {register_address}: {value}")
            return value

        finally:
            client.close()

    except ModbusException as e:
        logger.error(f"Modbus exception: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading Modbus: {e}")
        return None


def parse_modbus_registers(
    registers: list,
    data_type: str,
    byte_order: str = 'big',
    word_order: str = 'big'
) -> Optional[float]:
    """
    Parse Modbus registers into a value based on data type and byte/word order

    Args:
        registers: List of 16-bit register values
        data_type: Target data type
        byte_order: Byte order within each register ('big' or 'little')
        word_order: Register order for multi-register values ('big' or 'little')

    Returns:
        Parsed value as float
    """
    try:
        if data_type == 'uint16':
            # Single 16-bit unsigned integer
            return float(registers[0])

        elif data_type == 'int16':
            # Single 16-bit signed integer
            value = registers[0]
            if value >= 32768:  # Convert to signed
                value -= 65536
            return float(value)

        elif data_type == 'uint8_high':
            # High byte of 16-bit register (unsigned)
            if byte_order == 'big':
                return float((registers[0] >> 8) & 0xFF)
            else:  # little endian
                return float(registers[0] & 0xFF)

        elif data_type == 'uint8_low':
            # Low byte of 16-bit register (unsigned)
            if byte_order == 'big':
                return float(registers[0] & 0xFF)
            else:  # little endian
                return float((registers[0] >> 8) & 0xFF)

        elif data_type == 'int8_high':
            # High byte of 16-bit register (signed)
            if byte_order == 'big':
                value = (registers[0] >> 8) & 0xFF
            else:
                value = registers[0] & 0xFF
            if value >= 128:  # Convert to signed
                value -= 256
            return float(value)

        elif data_type == 'int8_low':
            # Low byte of 16-bit register (signed)
            if byte_order == 'big':
                value = registers[0] & 0xFF
            else:
                value = (registers[0] >> 8) & 0xFF
            if value >= 128:  # Convert to signed
                value -= 256
            return float(value)

        elif data_type == 'uint32':
            # 32-bit unsigned integer from 2 registers
            if word_order == 'big':
                high, low = registers[0], registers[1]
            else:
                low, high = registers[0], registers[1]

            # Convert to bytes and back to handle byte order
            if byte_order == 'big':
                bytes_data = struct.pack('>HH', high, low)
                value = struct.unpack('>I', bytes_data)[0]
            else:
                bytes_data = struct.pack('<HH', high, low)
                value = struct.unpack('<I', bytes_data)[0]
            return float(value)

        elif data_type == 'int32':
            # 32-bit signed integer from 2 registers
            if word_order == 'big':
                high, low = registers[0], registers[1]
            else:
                low, high = registers[0], registers[1]

            if byte_order == 'big':
                bytes_data = struct.pack('>HH', high, low)
                value = struct.unpack('>i', bytes_data)[0]
            else:
                bytes_data = struct.pack('<HH', high, low)
                value = struct.unpack('<i', bytes_data)[0]
            return float(value)

        elif data_type == 'float32':
            # 32-bit IEEE 754 float from 2 registers
            if word_order == 'big':
                high, low = registers[0], registers[1]
            else:
                low, high = registers[0], registers[1]

            if byte_order == 'big':
                bytes_data = struct.pack('>HH', high, low)
                value = struct.unpack('>f', bytes_data)[0]
            else:
                bytes_data = struct.pack('<HH', high, low)
                value = struct.unpack('<f', bytes_data)[0]
            return float(value)

        else:
            logger.error(f"Unknown data type: {data_type}")
            return None

    except Exception as e:
        logger.error(f"Error parsing Modbus registers: {e}")
        return None


def fetch_modbus_sensors(sensors_config: list) -> Dict[str, Dict[str, Any]]:
    """
    Fetch data from multiple Modbus TCP sensors

    Args:
        sensors_config: List of sensor configuration dicts

    Returns:
        Dictionary mapping param_name to {value, unit}
    """
    result = {}

    for sensor in sensors_config:
        try:
            param_name = sensor.get('param_name')
            if not param_name:
                logger.warning(f"Modbus sensor missing param_name: {sensor}")
                continue

            value = read_modbus_value(
                ip=sensor['ip'],
                port=sensor.get('port', 502),
                slave_id=sensor['slave_id'],
                register_type=sensor['register_type'],
                register_address=sensor['register_address'],
                data_type=sensor['data_type'],
                byte_order=sensor.get('byte_order', 'big'),
                word_order=sensor.get('word_order', 'big')
            )

            if value is not None:
                result[param_name] = {
                    'value': str(value),
                    'unit': sensor.get('unit', '')
                }
                logger.info(f"Modbus sensor {param_name}: {value} {sensor.get('unit', '')}")
            else:
                logger.error(f"Failed to read Modbus sensor {param_name} from {sensor.get('ip')}")

        except Exception as e:
            logger.error(f"Error fetching Modbus sensor {sensor.get('param_name', 'unknown')}: {e}")
            continue

    return result
