import json
import os
from typing import Tuple
from dotenv import load_dotenv

from .constants import SENSORS_FILE, logger

# Global environment config (loaded once at startup)
_env_config = None


def load_env_config() -> dict:
    """Load environment configuration from .env file (called once at startup)"""
    global _env_config

    if _env_config is not None:
        return _env_config

    # Load .env file
    load_dotenv()

    _env_config = {
        'token_id': os.getenv('TOKEN_ID', ''),
        'device_id': os.getenv('DEVICE_ID', ''),
        'station_id': os.getenv('STATION_ID', ''),
        'uid': os.getenv('UID',''),
        'public_key': os.getenv('PUBLIC_KEY', ''),
        'dev_mode': os.getenv('DEV_MODE', 'false').lower() in ('true', '1', 'yes'),
        'datapage_url': os.getenv('DATAPAGE_URL', ''),
        'endpoint': os.getenv('ENDPOINT', 'https://cems.cpcb.gov.in/v1.0/industry/data'),
        'error_endpoint_url': os.getenv('ERROR_ENDPOINT_URL', 'http://65.1.87.62/ocms/Cpcb/add_cpcberror'),
        'error_session_cookie': os.getenv('ERROR_SESSION_COOKIE', 'e1j7mnclaennlc5vqfr8ms2iiv1ng2i7')
    }

    logger.info("Environment configuration loaded from .env")
    return _env_config


def get_env(key: str, default=None):
    """Get environment variable value"""
    if _env_config is None:
        load_env_config()
    return _env_config.get(key, default)


def get_default_sensors_config() -> dict:
    """Get default sensors configuration"""
    return {
        "server_running": False,
        "sensors": [],
        "rtu_device": None  # Modbus RTU serial device config (only one device supported)
    }


def load_sensors_config() -> dict:
    """Load sensors configuration from sensors.json"""
    if not os.path.exists(SENSORS_FILE):
        default_config = get_default_sensors_config()
        save_sensors_config(default_config)
        return default_config

    try:
        with open(SENSORS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading sensors config: {e}, using defaults")
        return get_default_sensors_config()


def save_sensors_config(sensors_data: dict):
    """Save sensors configuration to sensors.json"""
    try:
        with open(SENSORS_FILE, 'w') as f:
            json.dump(sensors_data, f, indent=2)
        logger.info("Sensors configuration saved")
    except Exception as e:
        logger.error(f"Error saving sensors config: {e}")


def validate_sensors_config(sensors_data: dict) -> Tuple[bool, str]:
    """Validate sensors configuration"""
    if 'sensors' not in sensors_data:
        return False, "Missing 'sensors' field"

    if not isinstance(sensors_data['sensors'], list):
        return False, "'sensors' must be a list"

    # Check if there are any Modbus RTU sensors
    has_rtu_sensors = any(s.get('type') == 'modbus_rtu' for s in sensors_data['sensors'])

    # If there are RTU sensors, validate RTU device configuration
    if has_rtu_sensors:
        rtu_device = sensors_data.get('rtu_device')
        if not rtu_device:
            return False, "Modbus RTU sensors require rtu_device configuration"

        if not rtu_device.get('port'):
            return False, "RTU device missing port (e.g., COM7, /dev/ttyUSB0)"

    for idx, sensor in enumerate(sensors_data['sensors']):
        sensor_type = sensor.get('type', 'iq_web_connect')

        # Validate based on sensor type
        if sensor_type == 'iq_web_connect':
            if not all(k in sensor for k in ['sensor_id', 'param_name']):
                return False, f"IQ Web sensor {idx+1}: missing sensor_id or param_name"

        elif sensor_type == 'modbus_tcp':
            required_fields = ['ip', 'slave_id', 'register_type', 'register_address',
                             'data_type', 'param_name', 'unit']
            missing = [f for f in required_fields if f not in sensor or sensor[f] == '']
            if missing:
                return False, f"Modbus TCP sensor {idx+1}: missing {', '.join(missing)}"

        elif sensor_type == 'modbus_rtu':
            required_fields = ['slave_id', 'register_type', 'register_address',
                             'data_type', 'param_name', 'unit']
            missing = [f for f in required_fields if f not in sensor or sensor[f] == '']
            if missing:
                return False, f"Modbus RTU sensor {idx+1}: missing {', '.join(missing)}"

        else:
            return False, f"Sensor {idx+1}: unknown type '{sensor_type}'"

    return True, "Configuration valid"
