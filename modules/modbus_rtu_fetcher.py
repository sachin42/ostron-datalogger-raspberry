"""
Modbus RTU data fetcher for serial/RS485 communication
"""
import struct
from typing import Optional, Dict, Any
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

from .constants import logger


def read_modbus_rtu_value(
    client: ModbusSerialClient,
    slave_id: int,
    register_type: str,
    register_address: int,
    data_type: str,
    byte_order: str = 'big',
    word_order: str = 'big'
) -> Optional[float]:
    """
    Read a value from Modbus RTU device using existing client connection

    Args:
        client: Connected ModbusSerialClient instance
        slave_id: Slave ID/Unit ID (1-247)
        register_type: Type of register ('holding', 'input', 'coil', 'discrete')
        register_address: Register address to read
        data_type: Data type to read
        byte_order: Byte order for multi-byte values ('big' or 'little')
        word_order: Word order for multi-register values ('big' or 'little')

    Returns:
        Parsed value as float, or None if error
    """
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
                logger.error(f"Modbus RTU read error: {result}")
                return None
        elif register_type == 'discrete':
            result = client.read_discrete_inputs(register_address, 1, slave=slave_id)
            if not result.isError():
                return float(result.bits[0])
            else:
                logger.error(f"Modbus RTU read error: {result}")
                return None
        else:
            logger.error(f"Unsupported register type: {register_type}")
            return None

        if result.isError():
            logger.error(f"Modbus RTU read error: {result}")
            return None

        registers = result.registers

        # Parse the value using same logic as TCP
        from .modbus_fetcher import parse_modbus_registers
        value = parse_modbus_registers(registers, data_type, byte_order, word_order)

        logger.debug(f"Modbus RTU read slave {slave_id} reg {register_address}: {value}")
        return value

    except ModbusException as e:
        logger.error(f"Modbus RTU exception: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading Modbus RTU: {e}")
        return None


def fetch_modbus_rtu_sensors(rtu_device: dict, sensors_config: list) -> Dict[str, Dict[str, Any]]:
    """
    Fetch data from multiple Modbus RTU sensors on a single serial bus

    Args:
        rtu_device: RTU device configuration dict with port, baudrate, parity, etc.
        sensors_config: List of sensor configuration dicts

    Returns:
        Dictionary mapping param_name to {value, unit}
    """
    result = {}

    # Validate device configuration
    if not rtu_device or not rtu_device.get('port'):
        logger.error("Modbus RTU device not configured or missing port")
        return result

    port = rtu_device['port']
    baudrate = rtu_device.get('baudrate', 9600)
    parity = rtu_device.get('parity', 'N')
    stopbits = rtu_device.get('stopbits', 1)
    bytesize = rtu_device.get('bytesize', 8)
    timeout = rtu_device.get('timeout', 3)

    # Create serial client
    try:
        client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity=parity,
            stopbits=stopbits,
            bytesize=bytesize,
            timeout=timeout
        )

        if not client.connect():
            logger.error(f"Failed to connect to Modbus RTU device at {port}")
            return result

        try:
            # Read all sensors using the shared connection
            for sensor in sensors_config:
                try:
                    param_name = sensor.get('param_name')
                    if not param_name:
                        logger.warning(f"Modbus RTU sensor missing param_name: {sensor}")
                        continue

                    value = read_modbus_rtu_value(
                        client=client,
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
                        logger.info(f"Modbus RTU sensor {param_name} (slave {sensor['slave_id']}): {value} {sensor.get('unit', '')}")
                    else:
                        logger.error(f"Failed to read Modbus RTU sensor {param_name} from slave {sensor.get('slave_id')}")

                except Exception as e:
                    logger.error(f"Error fetching Modbus RTU sensor {sensor.get('param_name', 'unknown')}: {e}")
                    continue

        finally:
            client.close()

    except Exception as e:
        logger.error(f"Error creating Modbus RTU client: {e}")

    return result
