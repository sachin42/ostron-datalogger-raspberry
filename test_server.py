from flask import Flask, request, jsonify, render_template_string
import base64
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Util.Padding import unpad
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz

app = Flask(__name__)

# Load environment variables
load_dotenv()
TOKEN_ID = os.getenv('TOKEN_ID', 'Hvg_LrxeePXexh7TM76jQqWsWGRV4M4gvX1_tvKDMN4=')
DEVICE_ID = os.getenv('DEVICE_ID', 'device_7025')
STATION_ID = os.getenv('STATION_ID', 'station_8203')
PUBLIC_KEY_PEM = os.getenv('PUBLIC_KEY', '')
DEV_MODE = os.getenv('DEV_MODE', 'false').lower() in ('true', '1', 'yes')

# Constants
IST = pytz.timezone("Asia/Kolkata")

# Server configuration (can be changed via web UI)
server_config = {
    'mode': 'success',  # success, http_error, api_error
    'http_status': 500,  # For http_error mode
    'api_status': 10,   # For api_error mode (ODAMS status codes)
    'validate_credentials': True,  # Validate token, device, station
    'decode_signature': True  # Decode and display signature
}

# ODAMS API error responses
API_ERRORS = {
    10: "failed",
    102: "Invalid_Station",
    109: "Payload not encrypted properly",
    110: "Invalid unit",
    111: "Uploaded data is not matching with defined 15 min timeframe",
    112: "No calibration scheduled for this timestamp please contact cpcb",
    113: "signature key is missing in headers",
    114: "X-Device-Id key is missing in headers",
    115: "Public_Key is missing Generate the Key",
    116: "Device is not registered, Please register for the Industry",
    117: "Data cannot be pushed beyond 7 days",
    118: "Data cannot be pushed for future time",
    119: "Invalid Parameter",
    120: "Multiple Station Found in the Payload",
    121: "The Station and Device Mapping not Found in the Payload"
}

def decrypt_payload(encrypted_b64, token_id):
    """Decrypt AES payload"""
    try:
        key = SHA256.new(token_id.encode()).digest()
        cipher = AES.new(key, AES.MODE_ECB)
        encrypted = base64.b64decode(encrypted_b64)
        decrypted = unpad(cipher.decrypt(encrypted), 16)
        return decrypted.decode(), None
    except Exception as e:
        return None, str(e)

def decode_signature(signature_b64, public_key_pem):
    """Decode RSA signature"""
    try:
        encrypted_sig = base64.b64decode(signature_b64)
        # Note: Signature contains token_id$*timestamp, but we can't decrypt it without private key
        # We can only show it's present and its length
        return f"Signature present (length: {len(encrypted_sig)} bytes)"
    except Exception as e:
        return f"Signature decode error: {e}"

def validate_payload(data, device_id, station_id):
    """Validate payload structure and credentials"""
    errors = []

    try:
        # Check basic structure
        if 'data' not in data:
            errors.append("Missing 'data' field in payload")
            return errors

        if not isinstance(data['data'], list) or len(data['data']) == 0:
            errors.append("'data' field must be a non-empty array")
            return errors

        # Check station
        payload_station = data['data'][0].get('stationId', '')
        if payload_station != station_id:
            errors.append(f"Station mismatch: expected {station_id}, got {payload_station}")

        # Check device
        if 'device_data' in data['data'][0]:
            payload_device = data['data'][0]['device_data'][0].get('deviceId', '')
            if payload_device != device_id:
                errors.append(f"Device mismatch: expected {device_id}, got {payload_device}")

    except Exception as e:
        errors.append(f"Validation error: {e}")

    return errors


def validate_timestamp_alignment(timestamp_ms):
    """
    Validate timestamp alignment (Status 111)
    Production: Must align to 15-minute boundaries (XX:00, XX:15, XX:30, XX:45)
    Development: Must align to 1-minute boundaries
    """
    try:
        dt = datetime.fromtimestamp(timestamp_ms / 1000, IST)
        alignment_minutes = 1 if DEV_MODE else 15

        # Check if minute is aligned
        if dt.minute % alignment_minutes != 0:
            return False, f"Timestamp not aligned to {alignment_minutes}-minute boundary: {dt.strftime('%Y-%m-%d %H:%M:%S')}"

        # Check if seconds and microseconds are zero
        if dt.second != 0 or dt.microsecond != 0:
            return False, f"Timestamp has non-zero seconds/microseconds: {dt.strftime('%Y-%m-%d %H:%M:%S.%f')}"

        return True, None
    except Exception as e:
        return False, f"Invalid timestamp format: {e}"


def validate_timestamp_backdate(timestamp_ms):
    """Validate timestamp is not older than 7 days (Status 117)"""
    try:
        now = datetime.now(IST)
        now_ms = int(now.timestamp() * 1000)

        # Check if older than 7 days
        if now_ms - timestamp_ms > 7 * 24 * 60 * 60 * 1000:
            dt = datetime.fromtimestamp(timestamp_ms / 1000, IST)
            return False, f"Data older than 7 days: {dt.strftime('%Y-%m-%d %H:%M:%S')}"

        return True, None
    except Exception as e:
        return False, f"Invalid timestamp: {e}"


def validate_timestamp_future(timestamp_ms):
    """Validate timestamp is not in the future (Status 118)"""
    try:
        now = datetime.now(IST)
        now_ms = int(now.timestamp() * 1000)

        # Check if future timestamp
        if timestamp_ms > now_ms:
            dt = datetime.fromtimestamp(timestamp_ms / 1000, IST)
            return False, f"Future timestamp not allowed: {dt.strftime('%Y-%m-%d %H:%M:%S')}"

        return True, None
    except Exception as e:
        return False, f"Invalid timestamp: {e}"


def validate_parameters(params):
    """
    Validate parameter structure (Status 119)
    Each parameter must have: parameter, value, unit, timestamp, flag
    """
    required_fields = ['parameter', 'value', 'unit', 'timestamp', 'flag']

    for idx, param in enumerate(params):
        for field in required_fields:
            if field not in param:
                return False, f"Parameter {idx} missing required field: {field}"

        # Validate timestamp is a number
        try:
            int(param['timestamp'])
        except (ValueError, TypeError):
            return False, f"Parameter {idx} has invalid timestamp: {param.get('timestamp')}"

    return True, None


def validate_multiple_stations(data):
    """Validate only one station in payload (Status 120)"""
    try:
        if 'data' not in data or not isinstance(data['data'], list):
            return False, "Invalid payload structure"

        # Collect all unique station IDs
        stations = set()
        for item in data['data']:
            station_id = item.get('stationId')
            if station_id:
                stations.add(station_id)

        if len(stations) > 1:
            return False, f"Multiple stations found: {', '.join(stations)}"

        return True, None
    except Exception as e:
        return False, f"Validation error: {e}"


def validate_station_device_mapping(data):
    """
    Validate station and device mapping exists (Status 121)
    Payload must have stationId and deviceId in proper structure
    """
    try:
        if 'data' not in data or not isinstance(data['data'], list) or len(data['data']) == 0:
            return False, "Missing data array"

        station_item = data['data'][0]

        # Check stationId exists
        if 'stationId' not in station_item or not station_item['stationId']:
            return False, "Missing stationId in payload"

        # Check device_data exists
        if 'device_data' not in station_item or not isinstance(station_item['device_data'], list):
            return False, "Missing device_data array"

        if len(station_item['device_data']) == 0:
            return False, "Empty device_data array"

        # Check deviceId exists
        device_item = station_item['device_data'][0]
        if 'deviceId' not in device_item or not device_item['deviceId']:
            return False, "Missing deviceId in device_data"

        return True, None
    except Exception as e:
        return False, f"Validation error: {e}"

@app.route('/')
def index():
    """Web UI for configuring test server"""
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ODAMS Test Server</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 20px auto; padding: 20px; }
            h1 { color: #333; }
            .section { background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            label { display: block; margin: 10px 0 5px 0; font-weight: bold; }
            select, input[type="number"], input[type="checkbox"] { padding: 8px; margin-bottom: 10px; }
            select { width: 100%; }
            button { background: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px; }
            button:hover { background: #45a049; }
            .status { padding: 10px; border-radius: 4px; margin: 10px 0; }
            .success { background: #d4edda; color: #155724; }
            .error { background: #f8d7da; color: #721c24; }
            .info { background: #d1ecf1; color: #0c5460; }
            .credentials { background: #fff3cd; padding: 15px; border-radius: 4px; margin: 10px 0; }
            .log { background: #000; color: #0f0; padding: 15px; border-radius: 4px; font-family: monospace; max-height: 300px; overflow-y: auto; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h1>🧪 ODAMS Test Server</h1>

        <div class="section">
            <h2>Server Configuration</h2>
            <div class="config-grid">
                <div>
                    <label for="mode">Response Mode:</label>
                    <select id="mode" onchange="updateConfig()">
                        <option value="success" {{ 'selected' if config.mode == 'success' else '' }}>✅ Success Response</option>
                        <option value="http_error" {{ 'selected' if config.mode == 'http_error' else '' }}>❌ HTTP Error</option>
                        <option value="api_error" {{ 'selected' if config.mode == 'api_error' else '' }}>⚠️ API Error Response</option>
                    </select>

                    <div id="http_error_config" style="display: {{ 'block' if config.mode == 'http_error' else 'none' }};">
                        <label for="http_status">HTTP Status Code:</label>
                        <select id="http_status" onchange="updateConfig()">
                            <option value="400" {{ 'selected' if config.http_status == 400 else '' }}>400 Bad Request</option>
                            <option value="401" {{ 'selected' if config.http_status == 401 else '' }}>401 Unauthorized</option>
                            <option value="403" {{ 'selected' if config.http_status == 403 else '' }}>403 Forbidden</option>
                            <option value="404" {{ 'selected' if config.http_status == 404 else '' }}>404 Not Found</option>
                            <option value="500" {{ 'selected' if config.http_status == 500 else '' }}>500 Internal Server Error</option>
                            <option value="502" {{ 'selected' if config.http_status == 502 else '' }}>502 Bad Gateway</option>
                            <option value="503" {{ 'selected' if config.http_status == 503 else '' }}>503 Service Unavailable</option>
                        </select>
                    </div>

                    <div id="api_error_config" style="display: {{ 'block' if config.mode == 'api_error' else 'none' }};">
                        <label for="api_status">ODAMS Status Code:</label>
                        <select id="api_status" onchange="updateConfig()">
                            {% for code, msg in api_errors.items() %}
                            <option value="{{ code }}" {{ 'selected' if config.api_status == code else '' }}>{{ code }} - {{ msg }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>

                <div>
                    <label>
                        <input type="checkbox" id="validate_credentials" {{ 'checked' if config.validate_credentials else '' }} onchange="updateConfig()">
                        Validate Credentials (Station, Device, Token)
                    </label>

                    <label>
                        <input type="checkbox" id="decode_signature" {{ 'checked' if config.decode_signature else '' }} onchange="updateConfig()">
                        Decode & Display Signature
                    </label>
                </div>
            </div>

            <button onclick="updateConfig()">Apply Configuration</button>
            <button onclick="resetConfig()">Reset to Success</button>
        </div>

        <div class="section credentials">
            <h3>📋 Loaded Credentials from .env</h3>
            <table>
                <tr><th>Token ID</th><td>{{ token_id[:20] }}...</td></tr>
                <tr><th>Device ID</th><td>{{ device_id }}</td></tr>
                <tr><th>Station ID</th><td>{{ station_id }}</td></tr>
                <tr><th>Public Key</th><td>{{ 'Loaded (' + (public_key|length|string) + ' chars)' if public_key else 'Not loaded' }}</td></tr>
            </table>
        </div>

        <div class="section">
            <h3>📊 ODAMS API Error Codes Reference</h3>
            <p><strong>Legend:</strong>
                <span style="color: #28a745;">✓ Actual Validation</span> = Server validates payload and returns error if condition is true |
                <span style="color: #ffc107;">⚠ Simulation</span> = Error returned only when configured in test mode
            </p>
            <table>
                <thead>
                    <tr><th>Status Code</th><th>Type</th><th>Message</th></tr>
                </thead>
                <tbody>
                    <tr>
                        <td>10</td>
                        <td style="color: #ffc107;">⚠ Simulation</td>
                        <td>{{ api_errors[10] }}</td>
                    </tr>
                    <tr>
                        <td>102</td>
                        <td style="color: #ffc107;">⚠ Simulation</td>
                        <td>{{ api_errors[102] }}</td>
                    </tr>
                    <tr>
                        <td>109</td>
                        <td style="color: #28a745;">✓ Validation</td>
                        <td>{{ api_errors[109] }} (actual decryption test)</td>
                    </tr>
                    <tr>
                        <td>110</td>
                        <td style="color: #ffc107;">⚠ Simulation</td>
                        <td>{{ api_errors[110] }}</td>
                    </tr>
                    <tr>
                        <td>111</td>
                        <td style="color: #28a745;">✓ Validation</td>
                        <td>{{ api_errors[111] }} (checks timestamp alignment)</td>
                    </tr>
                    <tr>
                        <td>112</td>
                        <td style="color: #ffc107;">⚠ Simulation</td>
                        <td>{{ api_errors[112] }}</td>
                    </tr>
                    <tr>
                        <td>113</td>
                        <td style="color: #28a745;">✓ Validation</td>
                        <td>{{ api_errors[113] }} (checks signature header)</td>
                    </tr>
                    <tr>
                        <td>114</td>
                        <td style="color: #28a745;">✓ Validation</td>
                        <td>{{ api_errors[114] }} (checks X-Device-Id header)</td>
                    </tr>
                    <tr>
                        <td>115</td>
                        <td style="color: #28a745;">✓ Validation</td>
                        <td>{{ api_errors[115] }} (checks if PUBLIC_KEY exists)</td>
                    </tr>
                    <tr>
                        <td>116</td>
                        <td style="color: #ffc107;">⚠ Simulation</td>
                        <td>{{ api_errors[116] }}</td>
                    </tr>
                    <tr>
                        <td>117</td>
                        <td style="color: #28a745;">✓ Validation</td>
                        <td>{{ api_errors[117] }} (checks 7-day backdate limit)</td>
                    </tr>
                    <tr>
                        <td>118</td>
                        <td style="color: #28a745;">✓ Validation</td>
                        <td>{{ api_errors[118] }} (checks for future timestamps)</td>
                    </tr>
                    <tr>
                        <td>119</td>
                        <td style="color: #28a745;">✓ Validation</td>
                        <td>{{ api_errors[119] }} (validates parameter structure)</td>
                    </tr>
                    <tr>
                        <td>120</td>
                        <td style="color: #28a745;">✓ Validation</td>
                        <td>{{ api_errors[120] }} (checks for multiple stations)</td>
                    </tr>
                    <tr>
                        <td>121</td>
                        <td style="color: #28a745;">✓ Validation</td>
                        <td>{{ api_errors[121] }} (validates station/device mapping)</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="section info">
            <h3>ℹ️ Test Endpoints</h3>
            <p><strong>POST</strong> http://localhost:5000/v1.0/industry/data - Data submission endpoint</p>
            <p><strong>POST</strong> http://localhost:5000/ocms/Cpcb/add_cpcberror - Error reporting endpoint</p>
            <p>Configure these endpoints in your .env file:</p>
            <code>ENDPOINT=http://localhost:5000/v1.0/industry/data</code><br>
            <code>ERROR_ENDPOINT_URL=http://localhost:5000/ocms/Cpcb/add_cpcberror</code>
        </div>

        <div class="section" style="background: #e7f3ff;">
            <h3>🔍 How Validation Works</h3>
            <p><strong>Actual Validations (Always Active):</strong></p>
            <ul>
                <li><strong>Status 113, 114:</strong> Checks if required headers (signature, X-Device-Id) are present</li>
                <li><strong>Status 115:</strong> Checks if PUBLIC_KEY is configured in .env file</li>
                <li><strong>Status 109:</strong> Attempts to decrypt payload using TOKEN_ID from .env - fails if encryption is wrong</li>
                <li><strong>Status 121:</strong> Validates that payload has proper stationId and deviceId structure</li>
                <li><strong>Status 120:</strong> Checks if payload contains multiple stations (only one allowed)</li>
                <li><strong>Status 119:</strong> Validates each parameter has required fields: parameter, value, unit, timestamp, flag</li>
                <li><strong>Status 117:</strong> Checks if timestamp is older than 7 days (IST timezone)</li>
                <li><strong>Status 118:</strong> Checks if timestamp is in the future (IST timezone)</li>
                <li><strong>Status 111:</strong> Validates timestamp alignment:
                    <ul>
                        <li>DEV_MODE=true: Must align to 1-minute boundaries (XX:00, XX:01, XX:02, ...)</li>
                        <li>DEV_MODE=false: Must align to 15-minute boundaries (XX:00, XX:15, XX:30, XX:45)</li>
                    </ul>
                </li>
            </ul>
            <p><strong>Simulated Errors (Only When Configured):</strong></p>
            <ul>
                <li><strong>Status 10, 102, 110, 112, 116:</strong> Use "API Error Response" mode and select the error code</li>
                <li>These errors will only be returned if you explicitly configure them in the dropdown above</li>
                <li>If payload passes all validations, then the simulated error will be returned</li>
            </ul>
            <p><strong>Current Mode:</strong> DEV_MODE={{ 'true' if dev_mode else 'false' }} (timestamp alignment: {{ '1-minute' if dev_mode else '15-minute' }})</p>
        </div>

        <script>
        function updateConfig() {
            const mode = document.getElementById('mode').value;
            const http_status = document.getElementById('http_status').value;
            const api_status = document.getElementById('api_status').value;
            const validate_credentials = document.getElementById('validate_credentials').checked;
            const decode_signature = document.getElementById('decode_signature').checked;

            // Show/hide appropriate config sections
            document.getElementById('http_error_config').style.display = mode === 'http_error' ? 'block' : 'none';
            document.getElementById('api_error_config').style.display = mode === 'api_error' ? 'block' : 'none';

            fetch('/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    mode: mode,
                    http_status: parseInt(http_status),
                    api_status: parseInt(api_status),
                    validate_credentials: validate_credentials,
                    decode_signature: decode_signature
                })
            })
            .then(r => r.json())
            .then(data => {
                console.log('Config updated:', data);
            });
        }

        function resetConfig() {
            document.getElementById('mode').value = 'success';
            document.getElementById('validate_credentials').checked = true;
            document.getElementById('decode_signature').checked = true;
            updateConfig();
            location.reload();
        }
        </script>
    </body>
    </html>
    """

    return render_template_string(template,
                                   config=server_config,
                                   api_errors=API_ERRORS,
                                   token_id=TOKEN_ID,
                                   device_id=DEVICE_ID,
                                   station_id=STATION_ID,
                                   public_key=PUBLIC_KEY_PEM,
                                   dev_mode=DEV_MODE)

@app.route('/config', methods=['POST'])
def update_config():
    """Update server configuration"""
    data = request.json
    server_config.update(data)
    print(f"\n{'='*60}")
    print(f"🔧 Configuration Updated:")
    print(f"   Mode: {server_config['mode']}")
    if server_config['mode'] == 'http_error':
        print(f"   HTTP Status: {server_config['http_status']}")
    elif server_config['mode'] == 'api_error':
        print(f"   API Status: {server_config['api_status']} - {API_ERRORS.get(server_config['api_status'], 'Unknown')}")
    print(f"   Validate Credentials: {server_config['validate_credentials']}")
    print(f"   Decode Signature: {server_config['decode_signature']}")
    print(f"{'='*60}\n")
    return jsonify({"status": "updated", "config": server_config})

@app.route('/ocms/Cpcb/add_cpcberror', methods=['POST'])
def receive_error():
    """Error reporting endpoint for testing error and heartbeat messages"""
    print(f"\n{'='*80}")
    print(f"🚨 Error/Heartbeat Received")
    print(f"{'='*80}")

    try:
        # Print headers
        print(f"Headers:")
        for key, value in request.headers.items():
            print(f"  {key}: {value}")

        # Print form data
        if request.form:
            print(f"\nForm Data:")
            for key, value in request.form.items():
                print(f"  {key}: {value}")

        # Print raw data if present
        if request.data:
            print(f"\nRaw Data:")
            print(f"  {request.data.decode('utf-8', errors='replace')}")

        print(f"{'='*80}\n")

        return jsonify({"status": "success", "message": "Error received"}), 200

    except Exception as e:
        print(f"\n❌ Error processing request: {e}")
        print(f"{'='*80}\n")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/v1.0/industry/data', methods=['POST'])
def receive_data():
    """Main endpoint for receiving sensor data"""
    print(f"\n{'='*80}")
    print(f"📨 Received Request")
    print(f"{'='*80}")

    try:
        encrypted_payload = request.data.decode()
        device_id_header = request.headers.get('X-Device-Id', '')
        signature_header = request.headers.get('signature', '')

        print(f"Headers:")
        print(f"  X-Device-Id: {device_id_header}")
        print(f"  Signature: {signature_header[:50]}..." if len(signature_header) > 50 else f"  Signature: {signature_header}")
        print(f"  Content-Length: {len(encrypted_payload)}")

        # Decode signature if enabled
        if server_config['decode_signature'] and signature_header:
            sig_info = decode_signature(signature_header, PUBLIC_KEY_PEM)
            print(f"\n🔐 Signature Info:")
            print(f"  {sig_info}")

        # ========== ACTUAL VALIDATION (not simulated) ==========

        # Status 114: X-Device-Id key is missing in headers
        if not device_id_header:
            print(f"\n❌ [ACTUAL VALIDATION] Status 114: Missing X-Device-Id header")
            print(f"{'='*80}\n")
            return jsonify({"status": 114, "msg": API_ERRORS[114]}), 200

        # Status 113: signature key is missing in headers
        if not signature_header:
            print(f"\n❌ [ACTUAL VALIDATION] Status 113: Missing signature header")
            print(f"{'='*80}\n")
            return jsonify({"status": 113, "msg": API_ERRORS[113]}), 200

        # Status 115: Public_Key is missing Generate the Key
        if not PUBLIC_KEY_PEM or PUBLIC_KEY_PEM.strip() == '':
            print(f"\n❌ [ACTUAL VALIDATION] Status 115: Public key not configured in .env")
            print(f"{'='*80}\n")
            return jsonify({"status": 115, "msg": API_ERRORS[115]}), 200

        # Status 109: Payload not encrypted properly
        print(f"\n🔓 Decrypting payload...")
        plain_json, decrypt_error = decrypt_payload(encrypted_payload, TOKEN_ID)

        if decrypt_error:
            print(f"❌ [ACTUAL VALIDATION] Status 109: Decryption failed: {decrypt_error}")
            print(f"  Raw encrypted (first 100 chars): {encrypted_payload[:100]}...")
            print(f"{'='*80}\n")
            return jsonify({"status": 109, "msg": API_ERRORS[109]}), 200

        # Parse JSON
        try:
            data = json.loads(plain_json)
            print(f"\n✅ Decrypted and parsed successfully")
            print(f"📄 Payload:")
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError as e:
            print(f"❌ JSON parse error: {e}")
            return jsonify({"status": 10, "msg": "failed"}), 200

        # Status 121: The Station and Device Mapping not Found in the Payload
        valid, error_msg = validate_station_device_mapping(data)
        if not valid:
            print(f"\n❌ [ACTUAL VALIDATION] Status 121: {error_msg}")
            print(f"{'='*80}\n")
            return jsonify({"status": 121, "msg": API_ERRORS[121]}), 200

        # Status 120: Multiple Station Found in the Payload
        valid, error_msg = validate_multiple_stations(data)
        if not valid:
            print(f"\n❌ [ACTUAL VALIDATION] Status 120: {error_msg}")
            print(f"{'='*80}\n")
            return jsonify({"status": 120, "msg": API_ERRORS[120]}), 200

        # Extract parameters for validation
        try:
            params = data['data'][0]['device_data'][0].get('params', [])
            if not params:
                print(f"\n❌ No parameters found in payload")
                return jsonify({"status": 119, "msg": API_ERRORS[119]}), 200
        except (KeyError, IndexError, TypeError) as e:
            print(f"\n❌ Invalid payload structure: {e}")
            return jsonify({"status": 10, "msg": "failed"}), 200

        # Status 119: Invalid Parameter
        valid, error_msg = validate_parameters(params)
        if not valid:
            print(f"\n❌ [ACTUAL VALIDATION] Status 119: {error_msg}")
            print(f"{'='*80}\n")
            return jsonify({"status": 119, "msg": API_ERRORS[119]}), 200

        # Extract timestamp from first parameter (all should have same timestamp)
        timestamp_ms = params[0]['timestamp']
        dt_str = datetime.fromtimestamp(timestamp_ms / 1000, IST).strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n📅 Timestamp: {timestamp_ms} ({dt_str})")

        # Status 117: Data cannot be pushed beyond 7 days
        valid, error_msg = validate_timestamp_backdate(timestamp_ms)
        if not valid:
            print(f"\n❌ [ACTUAL VALIDATION] Status 117: {error_msg}")
            print(f"{'='*80}\n")
            return jsonify({"status": 117, "msg": API_ERRORS[117]}), 200

        # Status 118: Data cannot be pushed for future time
        valid, error_msg = validate_timestamp_future(timestamp_ms)
        if not valid:
            print(f"\n❌ [ACTUAL VALIDATION] Status 118: {error_msg}")
            print(f"{'='*80}\n")
            return jsonify({"status": 118, "msg": API_ERRORS[118]}), 200

        # Status 111: Uploaded data is not matching with defined 15 min timeframe
        valid, error_msg = validate_timestamp_alignment(timestamp_ms)
        if not valid:
            alignment = "1-minute" if DEV_MODE else "15-minute"
            print(f"\n❌ [ACTUAL VALIDATION] Status 111: {error_msg}")
            print(f"  Expected: {alignment} alignment (DEV_MODE={DEV_MODE})")
            print(f"{'='*80}\n")
            return jsonify({"status": 111, "msg": API_ERRORS[111]}), 200

        print(f"\n✅ All validations passed!")

        # ========== CREDENTIAL VALIDATION (if enabled) ==========

        # Validate device ID if enabled
        if server_config['validate_credentials']:
            if device_id_header != DEVICE_ID:
                print(f"\n❌ Status 116: Device ID mismatch:")
                print(f"  Expected: {DEVICE_ID}")
                print(f"  Received: {device_id_header}")
                print(f"{'='*80}\n")
                return jsonify({"status": 116, "msg": API_ERRORS[116]}), 200

        # Validate credentials in payload
        if server_config['validate_credentials']:
            validation_errors = validate_payload(data, DEVICE_ID, STATION_ID)
            if validation_errors:
                print(f"\n❌ Validation errors:")
                for err in validation_errors:
                    print(f"  - {err}")
                # Return appropriate error based on validation failure
                if 'Station mismatch' in validation_errors[0]:
                    print(f"{'='*80}\n")
                    return jsonify({"status": 102, "msg": API_ERRORS[102]}), 200
                elif 'Device mismatch' in validation_errors[0]:
                    print(f"{'='*80}\n")
                    return jsonify({"status": 116, "msg": API_ERRORS[116]}), 200
                else:
                    print(f"{'='*80}\n")
                    return jsonify({"status": 10, "msg": "failed"}), 200
            else:
                print(f"\n✅ Credentials validated successfully")

        # ========== SIMULATED ERRORS (configured mode) ==========

        # Return response based on configured mode
        if server_config['mode'] == 'http_error':
            http_status = server_config['http_status']
            print(f"\n⚠️  [SIMULATED] Returning HTTP error: {http_status}")
            print(f"{'='*80}\n")
            return jsonify({"error": f"HTTP {http_status} error"}), http_status

        elif server_config['mode'] == 'api_error':
            api_status = server_config['api_status']
            api_msg = API_ERRORS.get(api_status, "Unknown error")
            print(f"\n⚠️  [SIMULATED] Returning API error: {api_status} - {api_msg}")
            print(f"{'='*80}\n")
            return jsonify({"status": api_status, "msg": api_msg}), 200

        else:  # success mode
            print(f"\n✅ Returning success response")
            print(f"{'='*80}\n")
            return jsonify({"msg": "success", "status": 1}), 200

    except Exception as e:
        print(f"\n❌ Server error: {e}")
        print(f"{'='*80}\n")
        import traceback
        traceback.print_exc()
        return jsonify({"msg": "error", "status": 0}), 500

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🧪 ODAMS Test Server Starting")
    print("="*80)
    print(f"📋 Loaded from .env:")
    print(f"   TOKEN_ID: {TOKEN_ID[:20]}...")
    print(f"   DEVICE_ID: {DEVICE_ID}")
    print(f"   STATION_ID: {STATION_ID}")
    print(f"   PUBLIC_KEY: {'Loaded' if PUBLIC_KEY_PEM else 'Not loaded'}")
    print(f"   DEV_MODE: {DEV_MODE} (timestamp alignment: {'1-minute' if DEV_MODE else '15-minute'})")
    print(f"\n🌐 Web UI: http://localhost:5000")
    print(f"📡 Data Endpoint: http://localhost:5000/v1.0/industry/data")
    print(f"🚨 Error Endpoint: http://localhost:5000/ocms/Cpcb/add_cpcberror")
    print(f"\n💡 Configure the test server behavior via the web UI")
    print(f"\n✅ Actual Validations (always active):")
    print(f"   Status 109: Payload encryption")
    print(f"   Status 111: Timestamp alignment ({'1-min' if DEV_MODE else '15-min'})")
    print(f"   Status 113: Signature header presence")
    print(f"   Status 114: X-Device-Id header presence")
    print(f"   Status 115: Public key existence")
    print(f"   Status 117: 7-day backdate limit")
    print(f"   Status 118: Future timestamp check")
    print(f"   Status 119: Parameter structure")
    print(f"   Status 120: Multiple stations check")
    print(f"   Status 121: Station/device mapping")
    print(f"\n⚠️  Simulated Errors (configure via Web UI):")
    print(f"   Status 10, 102, 110, 112, 116")
    print("="*80 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=False)
