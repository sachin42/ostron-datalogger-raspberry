import json
import os
import shutil
from typing import Tuple

from .constants import CONFIG_FILE, logger
from .utils import acquire_lock


def get_default_config() -> dict:
    """Get default configuration"""
    return {
        "token_id": "",
        "device_id": "",
        "station_id": "",
        "public_key": "",
        "datapage_url": "",
        "endpoint": "https://cems.cpcb.gov.in/v1.0/industry/data",
        "sensors": [],
        "calibration_mode": False,
        "server_running": False,
        "last_fetch_success": "",
        "last_send_success": "",
        "total_sends": 0,
        "failed_sends": 0,
        "last_error": "",
        "error_endpoint_url": "http://65.1.87.62/ocms/Cpcb/add_cpcberror",
        "error_session_cookie": "e1j7mnclaennlc5vqfr8ms2iiv1ng2i7"
    }


def load_config() -> dict:
    """Load configuration with file locking"""
    if not os.path.exists(CONFIG_FILE):
        default_config = get_default_config()
        save_config(default_config)
        return default_config

    try:
        with acquire_lock():
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}, using defaults")
        return get_default_config()


def save_config(config: dict):
    """Save configuration with backup and file locking"""
    try:
        # Create backup
        if os.path.exists(CONFIG_FILE):
            backup_file = f"{CONFIG_FILE}.backup"
            shutil.copy2(CONFIG_FILE, backup_file)

        with acquire_lock():
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        # Restore from backup if save failed
        backup_file = f"{CONFIG_FILE}.backup"
        if os.path.exists(backup_file):
            shutil.copy2(backup_file, CONFIG_FILE)


def validate_config(config: dict) -> Tuple[bool, str]:
    """Validate configuration completeness"""
    required_fields = ['token_id', 'device_id', 'station_id', 'public_key', 'datapage_url']
    for field in required_fields:
        if not config.get(field):
            return False, f"Missing required field: {field}"

    if not config.get('sensors'):
        return False, "No sensors configured"

    for sensor in config['sensors']:
        if not all(k in sensor for k in ['sensor_id', 'param_name']):
            return False, "Invalid sensor configuration"

    return True, "Configuration valid"
