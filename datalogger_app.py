from flask import Flask, request, render_template_string, redirect, jsonify, send_from_directory
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
import threading
import time
import base64
import requests
import pytz
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Dict, List, Tuple, Optional
import shutil
import platform
import math

# Cross-platform file locking
try:
    import fcntl
    PLATFORM_WINDOWS = False
except ImportError:
    import msvcrt
    PLATFORM_WINDOWS = True

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Util.Padding import pad

# Set up rotating file handler
handler = RotatingFileHandler('datalogger.log', maxBytes=10*1024*1024, backupCount=5)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

app = Flask(__name__)
auth = HTTPBasicAuth()

CONFIG_FILE = 'config.json'
QUEUE_FILE = 'failed_queue.json'
LOCK_FILE = 'config.lock'

# Default credentials (change on first login)
users = {
    "admin": generate_password_hash("admin123")
}

# Time utilities
IST = pytz.timezone("Asia/Kolkata")

@auth.verify_password
def verify_password(username: str, password: str) -> bool:
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None

def acquire_lock(lock_file: str = LOCK_FILE, timeout: int = 10):
    """Context manager for cross-platform file locking"""
    class FileLock:
        def __init__(self, filename, timeout):
            self.filename = filename
            self.timeout = timeout
            self.file = None
        
        def __enter__(self):
            start_time = time.time()
            while True:
                try:
                    self.file = open(self.filename, 'w')
                    if PLATFORM_WINDOWS:
                        # Windows locking
                        msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        # Unix locking
                        fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return self
                except (IOError, OSError):
                    if self.file:
                        self.file.close()
                    if time.time() - start_time > self.timeout:
                        raise TimeoutError("Could not acquire lock")
                    time.sleep(0.1)
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.file:
                try:
                    if PLATFORM_WINDOWS:
                        msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
                except:
                    pass
                self.file.close()
    
    return FileLock(lock_file, timeout)

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

def load_queue() -> List[dict]:
    """Load failed transmission queue"""
    if not os.path.exists(QUEUE_FILE):
        return []
    
    try:
        with open(QUEUE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading queue: {e}")
        return []

def save_queue(queue: List[dict]):
    """Save failed transmission queue"""
    try:
        with open(QUEUE_FILE, 'w') as f:
            json.dump(queue, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving queue: {e}")

def get_aligned_timestamp_ms() -> int:
    """Get timestamp aligned to 15-minute intervals"""
    now = datetime.now(IST)
    aligned_minute = (now.minute // 15) * 15
    aligned = now.replace(minute=aligned_minute, second=0, microsecond=0)
    return int(aligned.timestamp() * 1000)

def get_signature_timestamp() -> str:
    """Get formatted timestamp for signature"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def validate_timestamp(ts_ms: int) -> bool:
    """Validate timestamp according to server rules"""
    now = datetime.now(IST)
    now_ms = int(now.timestamp() * 1000)

    # Backdate limit: older than 7 days not accepted
    if now_ms - ts_ms > 7 * 24 * 60 * 60 * 1000:
        return False

    # Future date not allowed
    if ts_ms > now_ms:
        return False

    # Check alignment to 15 min (or 30 sec in calibration, but since payload is aligned to 15 min, ok)
    dt = datetime.fromtimestamp(ts_ms / 1000, IST)
    if dt.minute % 15 != 0 or dt.second != 0 or dt.microsecond != 0:
        return False

    return True

def get_public_ip() -> str:
    """Get public IP address"""
    try:
        response = requests.get('https://api.ipify.org?format=text', timeout=5)
        return response.text.strip()
    except Exception as e:
        logger.warning(f"Failed to get public IP: {e}")
        return "Unknown"

def send_error_to_endpoint(tag: str, error_msg: str, config: dict, 
                           response_data: dict = None) -> bool:
    """Send error to HTTP endpoint with context"""
    try:
        endpoint = config.get('error_endpoint_url', 
                             'http://65.1.87.62/ocms/Cpcb/add_cpcberror')
        cookie = config.get('error_session_cookie', '')
        id = 861192078519884
        public_ip = get_public_ip()
        
        context = {
            'tag':  f"{tag} - UID:{id}",
            'error_message': error_msg,
            'device_id': config.get('device_id', ''),
            'station_id': config.get('station_id', ''),
            'public_ip': public_ip,
            'last_fetch_success': config.get('last_fetch_success', 'Never'),
            'last_send_success': config.get('last_send_success', 'Never'),
            'total_sends': config.get('total_sends', 0),
            'failed_sends': config.get('failed_sends', 0),
            'timestamp': datetime.now(IST).isoformat()
        }
        
        if response_data:
            context['response_data'] = response_data
        
        error_message = f"{tag} - UID:{id} - IP:{public_ip} - {error_msg}"
        
        headers = {
            'Cookie': f'ci_session={cookie}'
        }
        
        data = {
            'error': error_message
        }
        
        logger.error(f"Sending error to endpoint: {error_message}")
        logger.error(f"Context: {context}")
        
        response = requests.post(endpoint, headers=headers, data=data, timeout=10)
        logger.info(f"Error endpoint response: {response.status_code} - {response.text}")
        
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"Failed to send error to endpoint: {e}")
        return False

def build_plain_payload(sensors: dict, device_id: str, station_id: str,
                        lat: float = 28.6129, lon: float = 77.2295, flag: str = "U", align: bool = True) -> str:
    """Build plain JSON payload"""
    params = []
    if align:
        ts = get_aligned_timestamp_ms()
    else:
        ts = int(datetime.now(IST).timestamp() * 1000)
    for param, data in sensors.items():
        params.append({
            "parameter": param,
            "value": data['value'],
            "unit": data['unit'],
            "timestamp": ts,
            "flag": flag
        })
    payload = {
        "data": [
            {
                "stationId": station_id,
                "device_data": [
                    {
                        "deviceId": device_id,
                        "params": params
                    }
                ],
                "latitude": lat,
                "longitude": lon
            }
        ]
    }
    return json.dumps(payload, separators=(",", ":"))

def encrypt_payload(plain_json: str, token_id: str) -> str:
    """Encrypt payload using AES"""
    key = SHA256.new(token_id.encode()).digest()
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(plain_json.encode(), 16))
    return base64.b64encode(encrypted).decode()

def generate_signature(token_id: str, public_key_pem: str) -> str:
    """Generate RSA signature"""
    message = f"{token_id}$*{get_signature_timestamp()}".encode()
    pub_key = RSA.import_key(public_key_pem)
    cipher = PKCS1_OAEP.new(pub_key, hashAlgo=SHA256)
    encrypted = cipher.encrypt(message)
    return base64.b64encode(encrypted).decode()

def send_to_server(sensors: dict, device_id: str, station_id: str,
                   token_id: str, public_key_pem: str, config: dict,
                   endpoint: str = None,
                   max_retries: int = 3, flag: str = "U", align: bool = True) -> Tuple[bool, int, str]:
    """Send data to server with retry logic"""
    if not endpoint:
        endpoint = config.get('endpoint', "https://cems.cpcb.gov.in/v1.0/industry/data")
    if not sensors:
        logger.info("No sensor data to send")
        return False, 0, "No data"
    
    plain_json = build_plain_payload(sensors, device_id, station_id, flag=flag, align=align)
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
                return True, response.status_code, response.text
            
            # Don't retry on client errors (4xx)
            if 400 <= response.status_code < 500:
                error_msg = response.text
                send_error_to_endpoint("SERVER_ERROR", error_msg, config, 
                                       {'response': response.text, 'status_code': response.status_code})
                return False, response.status_code, response.text
            
            # Exponential backoff for retries
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    # All retries failed, send error report
    if last_response:
        error_msg = last_response
        send_error_to_endpoint("SERVER_ERROR", error_msg, config, 
                               {'response': last_response, 'status_code': last_status_code})
    else:
        error_msg = "Max retries exceeded - No response from server"
        send_error_to_endpoint("SERVER_ERROR", error_msg, config)
    
    return False, last_status_code, last_response if last_response else "Max retries exceeded"

def fetch_sensor_data(datapage_url: str, config_sensors: dict, config: dict) -> dict:
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
        send_error_to_endpoint("FETCH_ERROR", error_msg, config, 
                               {'http_status': e.response.status_code if hasattr(e, 'response') and e.response else None})
        return {}
    except Exception as e:
        error_msg = f"Parsing error: {str(e)}"
        logger.error(f"Error fetching data: {error_msg}")
        send_error_to_endpoint("FETCH_ERROR", error_msg, config)
        return {}

def retry_failed_transmissions(config: dict) -> int:
    """Retry queued failed transmissions after successful send"""
    queue = load_queue()
    if not queue:
        return 0

    successful = 0
    remaining = []
    endpoint = config.get('endpoint', "https://cems.cpcb.gov.in/v1.0/industry/data")
    token_id = config.get('token_id', '')
    public_key_pem = config.get('public_key', '')
    device_id = config.get('device_id', '')

    for item in queue:
        # Check if data is too old (backdate limit 7 days)
        current_ts = int(time.time() * 1000)
        if 'aligned_ts' in item and (current_ts - item['aligned_ts']) > 7 * 24 * 60 * 60 * 1000:
            logger.info(f"Skipping old queued data from {item['timestamp']}")
            continue

        try:
            # Regenerate signature with current time
            signature = generate_signature(token_id, public_key_pem)

            headers = {
                "Content-Type": "text/plain",
                "X-Device-Id": device_id,
                "signature": signature
            }

            response = requests.post(endpoint, data=item['encrypted_payload'],
                                   headers=headers, timeout=20)
            logger.info(f"Retry send status: {response.status_code} - {response.text}")

            success = False
            if response.status_code == 200:
                try:
                    data = json.loads(response.text.strip())
                    success = data.get('msg') == 'success' and data.get('status') == 1
                except json.JSONDecodeError:
                    pass

            if success:
                successful += 1
                logger.info(f"Successfully sent queued data from {item['timestamp']}")
            else:
                remaining.append(item)

        except Exception as e:
            logger.error(f"Retry failed: {e}")
            remaining.append(item)

    # Keep only last 100 failed items to prevent unbounded growth
    save_queue(remaining[-100:])
    return successful

def logger_thread():
    """Background thread for data logging"""
    last_send = 0
    config = load_config()  # Load once for alignment calc
    alignment_minutes = 1 if config.get('calibration_mode', False) else 15
    interval_seconds = alignment_minutes * 60
    now = datetime.now(IST)
    # Calculate next aligned time
    current_ts = now.timestamp()
    aligned_ts = math.ceil(current_ts / interval_seconds) * interval_seconds
    next_send_time = aligned_ts

    while True:
        try:
            config = load_config()

            if not config.get('server_running', False):
                time.sleep(5)
                continue

            current = time.time()

            should_send = False
            if last_send == 0:
                # First send: wait for next aligned time
                if current >= next_send_time:
                    should_send = True
                    last_send = next_send_time
                else:
                    sleep_time = min(5, next_send_time - current)
                    time.sleep(sleep_time)
                    continue
            else:
                # Subsequent sends: check interval
                if current - last_send >= interval_seconds:
                    should_send = True
                    last_send += interval_seconds
                else:
                    time.sleep(5)
                    continue

            if should_send:
                # Fetch new data
                config_sensors = {s['sensor_id']: s for s in config.get('sensors', [])}
                sensors = fetch_sensor_data(config.get('datapage_url', ''), config_sensors, config)
                
                if sensors:
                    # Update fetch success if we got all sensors
                    if len(sensors) == len(config_sensors):
                        config['last_fetch_success'] = datetime.now(IST).isoformat()
                    
                    logger.info(f"Fetched sensors: {sensors}")

                    # Send data
                    flag = "C" if config.get('calibration_mode', False) else "U"
                    align = not config.get('calibration_mode', False)
                    success, status, text = send_to_server(
                        sensors,
                        config.get('device_id', ''),
                        config.get('station_id', ''),
                        config.get('token_id', ''),
                        config.get('public_key', ''),
                        config,
                        flag=flag,
                        align=align
                    )

                    config['total_sends'] = config.get('total_sends', 0) + 1

                    if success:
                        config['last_send_success'] = datetime.now(IST).isoformat()
                        config['last_error'] = ""
                        logger.info("Data sent successfully")
                        # Retry queued data after successful send
                        retry_failed_transmissions(config)
                    else:
                        config['failed_sends'] = config.get('failed_sends', 0) + 1
                        config['last_error'] = f"Status {status}: {text}"

                        # Send error after 3 failed attempts
                        send_error_to_endpoint("SEND_FAILED", config['last_error'], config)

                        # Queue encrypted payload for retry (not in calibration mode)
                        if not config.get('calibration_mode', False):
                            flag = "C" if config.get('calibration_mode', False) else "U"
                            plain_json = build_plain_payload(sensors, config.get('device_id', ''), config.get('station_id', ''), flag=flag)
                            encrypted_payload = encrypt_payload(plain_json, config.get('token_id', ''))
                            aligned_ts = get_aligned_timestamp_ms()
                            queue = load_queue()
                            queue.append({
                                'encrypted_payload': encrypted_payload,
                                'timestamp': datetime.now(IST).isoformat(),
                                'aligned_ts': aligned_ts
                            })
                            save_queue(queue[-100:])  # Keep last 100
                        logger.error(f"Failed to send data: {text}")
                
                save_config(config)

            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Error in logger thread: {e}")
            time.sleep(10)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/health')
def health():
    """Health check endpoint"""
    config = load_config()
    queue = load_queue()
    
    health_status = {
        "status": "running" if config.get('server_running') else "stopped",
        "last_fetch": config.get('last_fetch_success', 'Never'),
        "last_send": config.get('last_send_success', 'Never'),
        "total_sends": config.get('total_sends', 0),
        "failed_sends": config.get('failed_sends', 0),
        "queued_items": len(queue),
        "last_error": config.get('last_error', ''),
        "config_valid": validate_config(config)[0]
    }
    
    return jsonify(health_status)

@app.route('/test_fetch')
@auth.login_required
def test_fetch():
    """Manual test of data fetching"""
    config = load_config()
    config_sensors = {s['sensor_id']: s for s in config.get('sensors', [])}
    sensors = fetch_sensor_data(config.get('datapage_url', ''), config_sensors, config)
    
    return jsonify({
        "success": len(sensors) > 0,
        "sensors": sensors,
        "expected_count": len(config_sensors),
        "actual_count": len(sensors)
    })

@app.route('/test_send')
@auth.login_required
def test_send():
    """Manual test of data sending"""
    config = load_config()
    config_sensors = {s['sensor_id']: s for s in config.get('sensors', [])}
    sensors = fetch_sensor_data(config.get('datapage_url', ''), config_sensors, config)
    
    if not sensors:
        return jsonify({"success": False, "error": "No sensor data fetched"})
    
    flag = "C" if config.get('calibration_mode', False) else "U"
    align = not config.get('calibration_mode', False)
    success, status, text = send_to_server(
        sensors,
        config.get('device_id', ''),
        config.get('station_id', ''),
        config.get('token_id', ''),
        config.get('public_key', ''),
        config,
        flag=flag,
        align=align
    )
    
    return jsonify({
        "success": success,
        "status": status,
        "response": text,
        "sensors": sensors
    })

@app.route('/', methods=['GET', 'POST'])
@auth.login_required
def index():
    if request.method == 'POST':
        config = load_config()
        config['token_id'] = request.form['token_id']
        config['device_id'] = request.form['device_id']
        config['station_id'] = request.form['station_id']
        config['public_key'] = request.form['public_key']
        config['datapage_url'] = request.form['datapage_url']
        config['endpoint'] = request.form.get('endpoint', '')
        config['calibration_mode'] = 'calibration' in request.form
        config['server_running'] = 'running' in request.form
        config['error_endpoint_url'] = request.form.get('error_endpoint_url', '')
        config['error_session_cookie'] = request.form.get('error_session_cookie', '')
        
        sensors = []
        for i in range(len(request.form.getlist('sensor_id[]'))):
            sensors.append({
                'sensor_id': request.form.getlist('sensor_id[]')[i],
                'unit': request.form.getlist('unit[]')[i],
                'param_name': request.form.getlist('param_name[]')[i]
            })
        config['sensors'] = sensors
        
        save_config(config)
        return redirect('/')
    
    config = load_config()
    queue = load_queue()
    sensor_values = {}
    
    try:
        config_sensors = {s['sensor_id']: s for s in config.get('sensors', [])}
        raw_sensors = fetch_sensor_data(config.get('datapage_url', ''), config_sensors, config)
        for sid, s in config_sensors.items():
            param = s['param_name']
            if param in raw_sensors:
                sensor_values[sid] = raw_sensors[param]['value']
    except Exception as e:
        logger.error(f"Error fetching sensor values for display: {e}")
        sensor_values = {}
    
    config_valid, config_msg = validate_config(config)
    
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Datalogger Setup</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 20px; }
            h1 { color: #333; text-align: center; }
            h2 { color: #555; }
            .container { max-width: 1200px; margin: auto; }
            .status-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
            .status-item { padding: 10px; background: #f9f9f9; border-radius: 4px; }
            .status-item label { font-weight: bold; color: #666; display: block; margin-bottom: 5px; }
            .status-item .value { color: #333; font-size: 14px; }
            .status-good { border-left: 4px solid #4CAF50; }
            .status-bad { border-left: 4px solid #f44336; }
            .status-warning { border-left: 4px solid #ff9800; }
            form { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            label { display: block; margin-top: 10px; font-weight: bold; color: #333; }
            input[type="text"], input[type="number"], textarea { width: 100%; padding: 8px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
            textarea { height: 100px; font-family: monospace; }
            input[type="checkbox"] { margin-top: 5px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            button { background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; margin-right: 5px; }
            button:hover { background-color: #45a049; }
            input[type="submit"] { background-color: #008CBA; margin-top: 20px; padding: 10px 20px; font-size: 16px; }
            input[type="submit"]:hover { background-color: #007B9A; }
            .remove-btn { background-color: #f44336; }
            .remove-btn:hover { background-color: #da190b; }
            .test-btn { background-color: #ff9800; }
            .test-btn:hover { background-color: #e68900; }
            .button-group { margin-top: 20px; }
            .error-msg { color: #f44336; padding: 10px; background: #ffebee; border-radius: 4px; margin-bottom: 10px; }
            .success-msg { color: #4CAF50; padding: 10px; background: #e8f5e9; border-radius: 4px; margin-bottom: 10px; }
        </style>
    </head>
    <body>
    <div class="container">
    <h1>Datalogger Configuration</h1>
    
    {% if not config_valid %}
    <div class="error-msg">⚠️ Configuration incomplete: {{ config_msg }}</div>
    {% endif %}
    
    <div class="status-card">
        <h2>System Status</h2>
        <div class="status-grid">
            <div class="status-item {% if config.server_running %}status-good{% else %}status-bad{% endif %}">
                <label>Server Status</label>
                <div class="value">{{ 'Running ✓' if config.server_running else 'Stopped ✗' }}</div>
            </div>
            <div class="status-item {% if config.last_fetch_success %}status-good{% else %}status-warning{% endif %}">
                <label>Last Fetch</label>
                <div class="value">{{ config.last_fetch_success or 'Never' }}</div>
            </div>
            <div class="status-item {% if config.last_send_success %}status-good{% else %}status-warning{% endif %}">
                <label>Last Send</label>
                <div class="value">{{ config.last_send_success or 'Never' }}</div>
            </div>
            <div class="status-item">
                <label>Total Sends</label>
                <div class="value">{{ config.get('total_sends', 0) }}</div>
            </div>
            <div class="status-item {% if config.get('failed_sends', 0) > 0 %}status-warning{% else %}status-good{% endif %}">
                <label>Failed Sends</label>
                <div class="value">{{ config.get('failed_sends', 0) }}</div>
            </div>
            <div class="status-item {% if queue_count > 0 %}status-warning{% else %}status-good{% endif %}">
                <label>Queued Items</label>
                <div class="value">{{ queue_count }}</div>
            </div>
        </div>
        {% if config.get('last_error') %}
        <div class="error-msg" style="margin-top: 15px;">
            <strong>Last Error:</strong> {{ config.last_error }}
        </div>
        {% endif %}
    </div>
    
    <div class="status-card">
        <div class="button-group">
            <button class="test-btn" onclick="testFetch()">Test Fetch</button>
            <button class="test-btn" onclick="testSend()">Test Send</button>
            <a href="/health" target="_blank"><button type="button">Health Check</button></a>
        </div>
    </div>
    
    <form method="post">
        <h2>Configuration</h2>
        <label>Token ID:</label><input type="text" name="token_id" value="{{ config.token_id }}" required>
        <label>Device ID:</label><input type="text" name="device_id" value="{{ config.device_id }}" required>
        <label>Station ID:</label><input type="text" name="station_id" value="{{ config.station_id }}" required>
        <label>Public Key:</label><textarea name="public_key" required>{{ config.public_key }}</textarea>
        <label>Datapage URL:</label><input type="text" name="datapage_url" value="{{ config.datapage_url }}" required>
        <label>Endpoint URL:</label><input type="text" name="endpoint" value="{{ config.get('endpoint', '') }}" placeholder="https://cems.cpcb.gov.in/v1.0/industry/data">

        <label>Calibration Mode (30 sec intervals):</label><input type="checkbox" name="calibration" {% if config.get('calibration_mode') %}checked{% endif %}>
        <label>Server Running:</label><input type="checkbox" name="running" {% if config.server_running %}checked{% endif %}>
        
        <h2>Error Reporting</h2>
        <label>Error Endpoint URL:</label><input type="text" name="error_endpoint_url" value="{{ config.get('error_endpoint_url', '') }}">
        <label>Error Session Cookie:</label><input type="text" name="error_session_cookie" value="{{ config.get('error_session_cookie', '') }}">
        
        <h2>Sensors</h2>
        <table id="sensors">
        <thead><tr><th>Sensor ID</th><th>Unit</th><th>Parameter Name</th><th>Current Value</th><th>Action</th></tr></thead>
        <tbody>
        {% for sensor in config.sensors %}
        <tr>
            <td><input type="text" name="sensor_id[]" value="{{ sensor.sensor_id }}" required></td>
            <td><input type="text" name="unit[]" value="{{ sensor.unit }}"></td>
            <td><input type="text" name="param_name[]" value="{{ sensor.param_name }}" required></td>
            <td><input type="text" readonly value="{{ sensor_values.get(sensor.sensor_id, '') }}"></td>
            <td><button type="button" class="remove-btn" onclick="removeRow(this)">Remove</button></td>
        </tr>
        {% endfor %}
        </tbody>
        </table>
        <button type="button" onclick="addRow()">Add Sensor</button><br>
        <input type="submit" value="Save Configuration">
    </form>
    </div>
    
    <script>
    function addRow() {
        var table = document.getElementById('sensors').getElementsByTagName('tbody')[0];
        var row = table.insertRow();
        row.innerHTML = '<td><input type="text" name="sensor_id[]" required></td><td><input type="text" name="unit[]"></td><td><input type="text" name="param_name[]" required></td><td><input type="text" readonly></td><td><button type="button" class="remove-btn" onclick="removeRow(this)">Remove</button></td>';
    }
    function removeRow(btn) {
        var row = btn.parentNode.parentNode;
        row.parentNode.removeChild(row);
    }
    function testFetch() {
        fetch('/test_fetch')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Fetch successful! Got ' + data.actual_count + ' of ' + data.expected_count + ' sensors.\\n\\n' + JSON.stringify(data.sensors, null, 2));
                } else {
                    alert('Fetch failed!');
                }
            })
            .catch(e => alert('Error: ' + e));
    }
    function testSend() {
        if (!confirm('This will send test data to the server. Continue?')) return;
        fetch('/test_send')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Send successful!\\n\\nStatus: ' + data.status + '\\nResponse: ' + data.response);
                } else {
                    alert('Send failed!\\n\\nStatus: ' + data.status + '\\nError: ' + data.response);
                }
            })
            .catch(e => alert('Error: ' + e));
    }
    </script>
    </body>
    </html>
    """
    return render_template_string(template, config=config, sensor_values=sensor_values, 
                                 config_valid=config_valid, config_msg=config_msg,
                                 queue_count=len(queue))

if __name__ == '__main__':
    # Start logger thread
    thread = threading.Thread(target=logger_thread, daemon=True)
    thread.start()
    
    logger.info("Datalogger application started")
    
    # Run web app
    app.run(host='0.0.0.0', port=9999, debug=False)