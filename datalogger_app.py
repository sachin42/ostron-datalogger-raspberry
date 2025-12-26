from flask import Flask, request, render_template_string, redirect
import json
import os
import threading
import time
import base64
import requests
import pytz
import logging
from datetime import datetime
from bs4 import BeautifulSoup

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Util.Padding import pad

# Set up logging to file
logging.basicConfig(filename='datalogger.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

CONFIG_FILE = 'config.json'

# Global flag for running
running = False

# Time utilities
IST = pytz.timezone("Asia/Kolkata")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}, using defaults")
            return get_default_config()
    # Create empty config on first run
    default_config = get_default_config()
    save_config(default_config)
    return default_config

def get_default_config():
    return {
        "token_id": "",
        "device_id": "",
        "station_id": "",
        "public_key": "",
        "datapage_url": "",
        "sensors": [],
        "fetch_send_interval_minutes": 15,
        "server_running": False,
        "last_fetch_success": "",
        "last_send_success": ""
    }

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")

def get_aligned_timestamp_ms():
    now = datetime.now(IST)
    aligned_minute = (now.minute // 15) * 15
    aligned = now.replace(minute=aligned_minute, second=0, microsecond=0)
    return int(aligned.timestamp() * 1000)

def get_signature_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def build_plain_payload(sensors, device_id, station_id, lat=28.6129, lon=77.2295):
    params = []
    ts = get_aligned_timestamp_ms()
    for param, data in sensors.items():
        params.append({
            "parameter": param,
            "value": data['value'],
            "unit": data['unit'],
            "timestamp": ts,
            "flag": "U"
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

def encrypt_payload(plain_json, token_id):
    key = SHA256.new(token_id.encode()).digest()
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(plain_json.encode(), 16))
    return base64.b64encode(encrypted).decode()

def generate_signature(token_id, public_key_pem):
    message = f"{token_id}$*{get_signature_timestamp()}".encode()
    pub_key = RSA.import_key(public_key_pem)
    cipher = PKCS1_OAEP.new(pub_key, hashAlgo=SHA256)
    encrypted = cipher.encrypt(message)
    return base64.b64encode(encrypted).decode()

def send_to_server(sensors, device_id, station_id, token_id, public_key_pem, endpoint="https://cems.cpcb.gov.in/v1.0/industry/data", log_enabled=True):
    if not sensors:
        if log_enabled:
            logging.info("No sensor data to send")
        return False, 0, ""
    plain_json = build_plain_payload(sensors, device_id, station_id)
    encrypted_payload = encrypt_payload(plain_json, token_id)
    signature = generate_signature(token_id, public_key_pem)

    headers = {
        "Content-Type": "text/plain",
        "X-Device-Id": device_id,
        "signature": signature
    }

    if log_enabled:
        logging.info(f"Plain JSON: {plain_json}")

    try:
        response = requests.post(endpoint, data=encrypted_payload, headers=headers, timeout=20)
        logging.info(f"Send status: {response.status_code} - {response.text}")
        print(f"Send status: {response.status_code} - {response.text}")
        success = False
        if response.status_code == 200:
            try:
                data = json.loads(response.text.strip())
                success = data.get('msg') == 'success' and data.get('status') == 1
            except json.JSONDecodeError:
                pass
        print(f"Success: {success}")
        return success, response.status_code, response.text
    except Exception as e:
        logging.error(f"Send error: {e}")
        print(f"Send error: {e}")
        return False, 0, str(e)

def fetch_sensor_data(datapage_url, config_sensors):
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
            sid_td = row.find('td', id=lambda x: x.startswith('SID') if x else False)
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
                            pass
        return sensors
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        print(f"Error fetching data: {e}")
        return {}

def logger_thread():
    last_send = 0
    while True:
        config = load_config()
        running = config.get('server_running', False)
        interval = config.get('fetch_send_interval_minutes', 15) * 60  # seconds
        current = time.time()
        if running and (current - last_send >= interval):
            config_sensors = {s['sensor_id']: s for s in config.get('sensors', [])}
            sensors = fetch_sensor_data(config.get('datapage_url', ''), config_sensors)
            if len(sensors) == len(config_sensors):
                config['last_fetch_success'] = datetime.now(IST).isoformat()
            if sensors:
                logging.info(f"Fetched sensors: {sensors}")
                success, status, text = send_to_server(sensors, config.get('device_id', ''), config.get('station_id', ''), config.get('token_id', ''), config.get('public_key', ''), log_enabled=True)
                if success:
                    config['last_send_success'] = datetime.now(IST).isoformat()
                    print(f"Set last_send_success: {config['last_send_success']}")
                logging.info("Data sent.")
            save_config(config)
            last_send = current
        time.sleep(5)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        config = load_config()
        config['token_id'] = request.form['token_id']
        config['device_id'] = request.form['device_id']
        config['station_id'] = request.form['station_id']
        config['public_key'] = request.form['public_key']
        config['datapage_url'] = request.form['datapage_url']
        config['fetch_send_interval_minutes'] = int(request.form['interval'])
        config['server_running'] = 'running' in request.form
        sensors = []
        for i in range(len(request.form.getlist('sensor_id[]'))):
            sensors.append({
                'sensor_id': request.form.getlist('sensor_id[]')[i],
                'unit': request.form.getlist('unit[]')[i],
                'param_name': request.form.getlist('param_name[]')[i]
            })
        config['sensors'] = sensors
        save_config(config)
        global running
        running = config['server_running']
        return redirect('/')
    
    config = load_config()
    sensor_values = {}
    try:
        config_sensors = {s['sensor_id']: s for s in config.get('sensors', [])}
        raw_sensors = fetch_sensor_data(config.get('datapage_url', ''), config_sensors)
        for sid, s in config_sensors.items():
            param = s['param_name']
            if param in raw_sensors:
                sensor_values[sid] = raw_sensors[param]['value']
    except Exception as e:
        print(f"Error fetching sensor values for display: {e}")
        sensor_values = {}
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Datalogger Setup</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 20px; }
            h1 { color: #333; text-align: center; }
            h2 { color: #555; }
            form { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 800px; margin: auto; }
            label { display: block; margin-top: 10px; font-weight: bold; color: #333; }
            input[type="text"], input[type="number"], textarea { width: 100%; padding: 8px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; }
            textarea { height: 100px; }
            input[type="checkbox"] { margin-top: 5px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            button { background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background-color: #45a049; }
            input[type="submit"] { background-color: #008CBA; margin-top: 20px; padding: 10px 20px; font-size: 16px; }
            input[type="submit"]:hover { background-color: #007B9A; }
            .remove-btn { background-color: #f44336; }
            .remove-btn:hover { background-color: #da190b; }
        </style>
    </head>
    <body>
    <h1>Datalogger Configuration</h1>
    <h2>Status</h2>
    <p>Last Fetch Success: {{ config.last_fetch_success }}</p>
    <p>Last Send Success: {{ config.last_send_success }}</p>
    <form method="post">
        <label>Token ID:</label><input type="text" name="token_id" value="{{ config.token_id }}">
        <label>Device ID:</label><input type="text" name="device_id" value="{{ config.device_id }}">
        <label>Station ID:</label><input type="text" name="station_id" value="{{ config.station_id }}">
        <label>Public Key:</label><textarea name="public_key">{{ config.public_key }}</textarea>
        <label>Datapage URL:</label><input type="text" name="datapage_url" value="{{ config.datapage_url }}">
        <label>Fetch/Send Interval (minutes):</label><input type="number" name="interval" value="{{ config.fetch_send_interval_minutes }}">
        <label>Server Running:</label><input type="checkbox" name="running" {% if config.server_running %}checked{% endif %}>
        <h2>Sensors</h2>
        <table id="sensors">
        <thead><tr><th>Sensor ID</th><th>Unit</th><th>Parameter Name</th><th>Current Value</th><th>Action</th></tr></thead>
        <tbody>
        {% for sensor in config.sensors %}
        <tr>
            <td><input type="text" name="sensor_id[]" value="{{ sensor.sensor_id }}"></td>
            <td><input type="text" name="unit[]" value="{{ sensor.unit }}"></td>
            <td><input type="text" name="param_name[]" value="{{ sensor.param_name }}"></td>
            <td><input type="text" readonly value="{{ sensor_values.get(sensor.sensor_id, '') }}"></td>
            <td><button type="button" class="remove-btn" onclick="removeRow(this)">Remove</button></td>
        </tr>
        {% endfor %}
        </tbody>
        </table>
        <button type="button" onclick="addRow()">Add Sensor</button><br>
        <input type="submit" value="Save">
    </form>
    <script>
    function addRow() {
        var table = document.getElementById('sensors').getElementsByTagName('tbody')[0];
        var row = table.insertRow();
        row.innerHTML = '<td><input type="text" name="sensor_id[]"></td><td><input type="text" name="unit[]"></td><td><input type="text" name="param_name[]"></td><td><input type="text" readonly></td><td><button type="button" class="remove-btn" onclick="removeRow(this)">Remove</button></td>';
    }
    function removeRow(btn) {
        var row = btn.parentNode.parentNode;
        row.parentNode.removeChild(row);
    }
    </script>
    </body>
    </html>
    """
    return render_template_string(template, config=config, sensor_values=sensor_values)

if __name__ == '__main__':
    # Start logger thread
    thread = threading.Thread(target=logger_thread, daemon=True)
    thread.start()
    # Run web app
    app.run(host='0.0.0.0', port=9999, debug=False)