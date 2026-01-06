import json
import time
import requests
from datetime import datetime
from typing import Tuple, Dict, Any
from bs4 import BeautifulSoup

from .constants import IST, logger
from .config import get_env
from .status import status
from .crypto import encrypt_payload, generate_signature
from .payload import build_plain_payload
from .modbus_fetcher import fetch_modbus_sensors


def get_public_ip() -> str:
    """Get public IP address"""
    try:
        response = requests.get('https://api.ipify.org?format=text', timeout=5)
        return response.text.strip()
    except Exception as e:
        logger.warning(f"Failed to get public IP: {e}")
        return "Unknown"


def send_error_to_endpoint(tag: str, error_msg: str) -> bool:
    """Send error to HTTP endpoint with context"""
    try:
        endpoint = get_env('error_endpoint_url', 'http://65.1.87.62/ocms/Cpcb/add_cpcberror')
        cookie = get_env('error_session_cookie', '')      
        public_ip = get_public_ip()
        error_message = f"{tag} - UID:{get_env('uid','')} - IP:{public_ip} - Message:{error_msg} - Time:{datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}"
        
        headers = {
            'Cookie': f'ci_session={cookie}'
        }

        data = {
            'error': error_message
        }

        if tag != "HEARTBEAT":
            logger.error(f"Sending error to endpoint: {error_message}")
        else:
            logger.debug(f"Sending heartbeat to endpoint: {error_message}")

        response = requests.post(endpoint, headers=headers, data=data, timeout=10)
        logger.debug(f"Endpoint response: {response.status_code} - {response.text}")

        return response.status_code == 200

    except Exception as e:
        logger.error(f"Failed to send error to endpoint: {e}")
        return False


def send_to_server(sensors: dict, endpoint: str = None, max_retries: int = 3) -> Tuple[bool, int, str, bool]:
    """
    Send data to server with retry logic

    Returns:
        Tuple[bool, int, str, bool]: (success, status_code, response_text, should_queue)
        - should_queue = True if data should be queued for retry (4xx or 5xx after retries)
        - should_queue = False if it's a data error (200 with wrong response)
    """
    if not endpoint:
        endpoint = get_env('endpoint', "https://cems.cpcb.gov.in/v1.0/industry/data")

    if not sensors:
        logger.warning("No sensor data to send")
        return False, 0, "No data", False

    device_id = get_env('device_id', '')
    station_id = get_env('station_id', '')
    token_id = get_env('token_id', '')
    public_key_pem = get_env('public_key', '')

    plain_json = build_plain_payload(sensors, device_id, station_id)
    last_response = None
    last_status_code = 0

    for attempt in range(max_retries):
        try:
            encrypted_payload = encrypt_payload(plain_json, token_id)
            signature = generate_signature(token_id, public_key_pem)

            headers = {
                "Content-Type": "text/plain",
                "X-Device-Id": device_id,
                "signature": signature
            }

            logger.info(f"Attempt {attempt + 1}/{max_retries} - Plain JSON: {plain_json}")

            response = requests.post(endpoint, data=encrypted_payload,
                                     headers=headers, timeout=20)
            logger.info(f"Send status: {response.status_code} - {response.text}")

            last_response = response.text
            last_status_code = response.status_code

            success = False
            if response.status_code == 200:
                try:
                    data = json.loads(response.text.strip())
                    success = data.get('msg') == 'success' and data.get('status') == 1
                except json.JSONDecodeError:
                    pass

            if success:
                return True, response.status_code, response.text, False

            # 200 but wrong response - data error, don't queue, don't retry
            if response.status_code == 200:
                logger.error(f"Data error - 200 OK but wrong response: {response.text}")
                return False, response.status_code, response.text, False

            # Don't retry on client errors (4xx), but DO queue
            if 400 <= response.status_code < 500:
                logger.error(f"Client error {response.status_code}: {response.text}")
                return False, response.status_code, response.text, True

            # Server errors (5xx) or other - retry with exponential backoff
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    # All retries failed - queue for later
    error_msg = last_response if last_response else "Max retries exceeded - No response from server"
    logger.error(f"All retries failed: {error_msg}")
    return False, last_status_code, error_msg, True


def fetch_sensor_data(datapage_url: str, config_sensors: dict) -> dict:
    """Fetch sensor data from webpage"""
    try:
        if datapage_url.startswith('file://'):
            file_path = datapage_url[7:]
            with open(file_path, 'r', encoding='utf-8') as f:
                html = f.read()
        else:
            response = requests.get(datapage_url, timeout=10)
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, 'html.parser')
        sensors = {}

        for row in soup.find_all('tr', class_=['EvenRow', 'OddRow']):
            sid_td = row.find('td', id=lambda x: x and x.startswith('SID'))
            if sid_td:
                sid = sid_td.text.strip()
                if sid in config_sensors:
                    num = ''.join(filter(str.isdigit, sid_td['id']))
                    mval_td = row.find('td', {'id': f'MVAL{num}'})
                    munit_td = row.find('td', {'id': f'MUNIT{num}'})

                    if mval_td:
                        param_api = config_sensors[sid]['param_name']
                        try:
                            value = float(mval_td.text.strip())
                            unit = config_sensors[sid]['unit'] or (munit_td.text.strip() if munit_td else '')
                            sensors[param_api] = {'value': value, 'unit': unit}
                        except ValueError:
                            logger.warning(f"Invalid value for sensor {sid}")

        return sensors
    except requests.RequestException as e:
        error_msg = f"Network error: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg = f"HTTP {e.response.status_code}: {str(e)}"
        logger.error(f"Error fetching data: {error_msg}")
        send_error_to_endpoint("FETCH_ERROR", error_msg,
                               {'http_status': e.response.status_code if hasattr(e, 'response') and e.response else None})
        return {}
    except Exception as e:
        error_msg = f"Parsing error: {str(e)}"
        logger.error(f"Error fetching data: {error_msg}")
        send_error_to_endpoint("FETCH_ERROR", error_msg)
        return {}


def fetch_all_sensors(sensors_config: dict) -> Dict[str, Dict[str, Any]]:
    """
    Fetch data from all configured sensors (multiple types)

    Args:
        sensors_config: Complete sensors configuration dict with 'sensors' list

    Returns:
        Dictionary mapping param_name to {value, unit}
    """
    all_sensors = {}

    try:
        sensors_list = sensors_config.get('sensors', [])

        # Separate sensors by type
        iq_web_sensors = {}
        modbus_tcp_sensors = []
        modbus_rtu_sensors = []

        for sensor in sensors_list:
            sensor_type = sensor.get('type', 'iq_web_connect')  # Default to IQ Web for backward compatibility

            if sensor_type == 'iq_web_connect':
                # Build config_sensors dict for IQ Web Connect
                sensor_id = sensor.get('sensor_id')
                if sensor_id:
                    iq_web_sensors[sensor_id] = {
                        'param_name': sensor.get('param_name'),
                        'unit': sensor.get('unit', '')
                    }

            elif sensor_type == 'modbus_tcp':
                modbus_tcp_sensors.append(sensor)

            elif sensor_type == 'modbus_rtu':
                modbus_rtu_sensors.append(sensor)

        # Fetch IQ Web Connect sensors
        if iq_web_sensors:
            datapage_url = get_env('datapage_url', '')
            if datapage_url:
                iq_data = fetch_sensor_data(datapage_url, iq_web_sensors)
                all_sensors.update(iq_data)
                logger.debug(f"Fetched {len(iq_data)} IQ Web Connect sensors")
            else:
                logger.warning("DATAPAGE_URL not configured, skipping IQ Web Connect sensors")

        # Fetch Modbus TCP sensors
        if modbus_tcp_sensors:
            modbus_data = fetch_modbus_sensors(modbus_tcp_sensors)
            all_sensors.update(modbus_data)
            logger.debug(f"Fetched {len(modbus_data)} Modbus TCP sensors")

        # Fetch Modbus RTU sensors
        if modbus_rtu_sensors:
            from .modbus_rtu_fetcher import fetch_modbus_rtu_sensors
            rtu_device = sensors_config.get('rtu_device')
            if rtu_device:
                rtu_data = fetch_modbus_rtu_sensors(rtu_device, modbus_rtu_sensors)
                all_sensors.update(rtu_data)
                logger.debug(f"Fetched {len(rtu_data)} Modbus RTU sensors")
            else:
                logger.warning("RTU device not configured, skipping Modbus RTU sensors")

        logger.debug(f"Total sensors fetched: {len(all_sensors)}")
        return all_sensors

    except Exception as e:
        logger.error(f"Error in fetch_all_sensors: {e}")
        return {}
