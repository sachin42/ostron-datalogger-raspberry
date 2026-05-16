"""
Waveshare Modbus RTU Analog Input 8CH Server
Reads 4-20mA analog inputs and serves data via REST API
with configurable linear scaling (e.g., 4-20mA to 0-150 m³/hr)
"""

from flask import Flask, jsonify, render_template_string, request
from pymodbus.client import ModbusSerialClient
import json
import threading
import time
import os
from datetime import datetime

app = Flask(__name__)

# Configuration file for channel mappings
CONFIG_FILE = 'analog_config.json'

# Global state
channel_data = {
    'timestamp': None,
    'channels': {}
}
data_lock = threading.Lock()
device_connected = False

# Default configuration
def get_default_config():
    return {
        'device': {
            'port': 'COM31',  # Change to /dev/ttyUSB0 for Linux
            'baudrate': 9600,
            'parity': 'N',
            'stopbits': 1,
            'bytesize': 8,
            'timeout': 1,
            'slave_id': 1
        },
        'channels': [
            {
                'id': 1,
                'name': 'Channel 1',
                'enabled': True,
                'min_value': 0,
                'max_value': 100,
                'unit': 'm³/hr',
                'decimals': 2
            },
            {
                'id': 2,
                'name': 'Channel 2',
                'enabled': True,
                'min_value': 0,
                'max_value': 100,
                'unit': 'm³/hr',
                'decimals': 2
            },
            {
                'id': 3,
                'name': 'Channel 3',
                'enabled': False,
                'min_value': 0,
                'max_value': 100,
                'unit': 'm³/hr',
                'decimals': 2
            },
            {
                'id': 4,
                'name': 'Channel 4',
                'enabled': False,
                'min_value': 0,
                'max_value': 100,
                'unit': 'm³/hr',
                'decimals': 2
            },
            {
                'id': 5,
                'name': 'Channel 5',
                'enabled': False,
                'min_value': 0,
                'max_value': 100,
                'unit': 'm³/hr',
                'decimals': 2
            },
            {
                'id': 6,
                'name': 'Channel 6',
                'enabled': False,
                'min_value': 0,
                'max_value': 100,
                'unit': 'm³/hr',
                'decimals': 2
            },
            {
                'id': 7,
                'name': 'Channel 7',
                'enabled': False,
                'min_value': 0,
                'max_value': 100,
                'unit': 'm³/hr',
                'decimals': 2
            },
            {
                'id': 8,
                'name': 'Channel 8',
                'enabled': False,
                'min_value': 0,
                'max_value': 100,
                'unit': 'm³/hr',
                'decimals': 2
            }
        ],
        'read_interval': 2  # seconds
    }


def load_config():
    """Load configuration from file or create default"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}, using defaults")
            return get_default_config()
    else:
        config = get_default_config()
        save_config(config)
        return config


def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def scale_4_20ma_to_value(raw_ua, min_value, max_value):
    """
    Convert 4-20mA (4000-20000 uA) to engineering units
    Linear scaling: value = ((current - 4000) / 16000) * (max - min) + min
    """
    if raw_ua is None:
        return None

    # Clamp to valid range
    raw_ua = max(4000, min(20000, raw_ua))

    # Linear interpolation
    # 4mA (4000 uA) = min_value
    # 20mA (20000 uA) = max_value
    percentage = (raw_ua - 4000) / 16000
    value = percentage * (max_value - min_value) + min_value

    return value


def read_analog_channels(config):
    """Read all analog channels from Modbus device"""
    global device_connected

    device_cfg = config['device']

    try:
        # Create Modbus client
        client = ModbusSerialClient(
            port=device_cfg['port'],
            baudrate=device_cfg['baudrate'],
            parity=device_cfg['parity'],
            stopbits=device_cfg['stopbits'],
            bytesize=device_cfg['bytesize'],
            timeout=device_cfg['timeout']
        )

        if not client.connect():
            device_connected = False
            print(f"Failed to connect to {device_cfg['port']}")
            return None

        device_connected = True

        # Read input registers 0x0000-0x0007 (8 channels)
        # Function code 04 (Read Input Registers)
        result = client.read_input_registers(
            address=0x0000,
            count=8,
            slave=device_cfg['slave_id']
        )

        if result.isError():
            print(f"Error reading registers: {result}")
            client.close()
            device_connected = False
            return None

        # Get raw values (in uA)
        raw_values = result.registers

        client.close()

        # Process each channel with scaling
        channels = {}
        for ch_config in config['channels']:
            ch_id = ch_config['id']
            ch_index = ch_id - 1  # 0-indexed

            if ch_index >= len(raw_values):
                continue

            raw_ua = raw_values[ch_index]

            # Calculate scaled value
            scaled_value = scale_4_20ma_to_value(
                raw_ua,
                ch_config['min_value'],
                ch_config['max_value']
            )

            if scaled_value is not None:
                scaled_value = round(scaled_value, ch_config.get('decimals', 2))

            channels[ch_id] = {
                'id': ch_id,
                'name': ch_config['name'],
                'enabled': ch_config['enabled'],
                'raw_ua': raw_ua,
                'raw_ma': round(raw_ua / 1000, 2),
                'value': scaled_value,
                'unit': ch_config['unit'],
                'min_range': ch_config['min_value'],
                'max_range': ch_config['max_value']
            }

        return channels

    except Exception as e:
        print(f"Exception reading channels: {e}")
        device_connected = False
        return None


def data_reader_thread():
    """Background thread to continuously read from device"""
    global channel_data

    print("Data reader thread started")

    while True:
        try:
            config = load_config()
            read_interval = config.get('read_interval', 2)

            channels = read_analog_channels(config)

            if channels:
                with data_lock:
                    channel_data = {
                        'timestamp': datetime.now().isoformat(),
                        'channels': channels
                    }

            time.sleep(read_interval)

        except Exception as e:
            print(f"Error in data reader thread: {e}")
            time.sleep(5)


# ============== REST API Endpoints ==============

@app.route('/api/channels', methods=['GET'])
def api_get_all_channels():
    """Get data for all channels"""
    with data_lock:
        data = channel_data.copy()

    data['device_connected'] = device_connected
    return jsonify(data)


@app.route('/api/channel/<int:channel_id>', methods=['GET'])
def api_get_channel(channel_id):
    """Get data for specific channel"""
    with data_lock:
        channels = channel_data.get('channels', {})
        channel = channels.get(channel_id)

    if channel:
        return jsonify({
            'timestamp': channel_data.get('timestamp'),
            'channel': channel,
            'device_connected': device_connected
        })
    else:
        return jsonify({'error': f'Channel {channel_id} not found'}), 404


@app.route('/api/config', methods=['GET'])
def api_get_config():
    """Get current configuration"""
    config = load_config()
    return jsonify(config)


@app.route('/api/config', methods=['POST'])
def api_save_config():
    """Save configuration"""
    try:
        config = request.get_json()
        if save_config(config):
            return jsonify({'status': 'success', 'message': 'Configuration saved'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to save configuration'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/status', methods=['GET'])
def api_status():
    """Get server and device status"""
    config = load_config()
    return jsonify({
        'server_running': True,
        'device_connected': device_connected,
        'device_port': config['device']['port'],
        'read_interval': config['read_interval'],
        'last_update': channel_data.get('timestamp')
    })


# ============== Web UI ==============

@app.route('/')
def index():
    """Web UI for configuration and monitoring"""
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Analog Acquisition Server</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }
            h1 { color: #333; margin-bottom: 20px; }

            .status-bar {
                background: white;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }

            .status-item {
                display: inline-block;
                margin-right: 20px;
            }

            .status-indicator {
                display: inline-block;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                margin-right: 5px;
            }

            .connected { background: #4CAF50; }
            .disconnected { background: #f44336; }

            .tabs {
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }

            .tab-buttons {
                display: flex;
                border-bottom: 1px solid #ddd;
            }

            .tab-button {
                flex: 1;
                padding: 15px;
                border: none;
                background: white;
                cursor: pointer;
                font-size: 14px;
                font-weight: bold;
                transition: background 0.3s;
            }

            .tab-button:hover { background: #f5f5f5; }
            .tab-button.active { background: #2196F3; color: white; }

            .tab-content {
                display: none;
                padding: 20px;
            }

            .tab-content.active { display: block; }

            .channel-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }

            .channel-card {
                background: #f9f9f9;
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 15px;
            }

            .channel-card.enabled { border-color: #4CAF50; }
            .channel-card.disabled { opacity: 0.6; }

            .channel-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }

            .channel-name { font-weight: bold; font-size: 16px; }
            .channel-id { color: #666; font-size: 12px; }

            .channel-value {
                font-size: 32px;
                font-weight: bold;
                color: #2196F3;
                margin: 10px 0;
            }

            .channel-raw {
                font-size: 12px;
                color: #666;
            }

            .config-section {
                background: #f9f9f9;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }

            .config-section h3 {
                margin-bottom: 15px;
                color: #333;
            }

            .form-row {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-bottom: 15px;
            }

            .form-group {
                display: flex;
                flex-direction: column;
            }

            label {
                font-weight: bold;
                margin-bottom: 5px;
                font-size: 14px;
                color: #555;
            }

            input[type="text"],
            input[type="number"],
            select {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }

            input[type="checkbox"] {
                width: 20px;
                height: 20px;
                cursor: pointer;
            }

            button {
                background: #4CAF50;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: bold;
                transition: background 0.3s;
            }

            button:hover { background: #45a049; }
            button:disabled { background: #ccc; cursor: not-allowed; }

            .button-group {
                display: flex;
                gap: 10px;
                margin-top: 20px;
            }

            .message {
                padding: 12px;
                border-radius: 4px;
                margin-top: 15px;
                display: none;
            }

            .message.success { background: #d4edda; color: #155724; }
            .message.error { background: #f8d7da; color: #721c24; }

            .device-config {
                background: #e3f2fd;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <h1>📊 Analog Acquisition Server</h1>

        <div class="status-bar">
            <div class="status-item">
                <span class="status-indicator" id="deviceStatus"></span>
                <strong>Device:</strong> <span id="deviceStatusText">Checking...</span>
            </div>
            <div class="status-item">
                <strong>Port:</strong> <span id="devicePort">-</span>
            </div>
            <div class="status-item">
                <strong>Last Update:</strong> <span id="lastUpdate">-</span>
            </div>
            <div class="status-item">
                <strong>Read Interval:</strong> <span id="readInterval">-</span>s
            </div>
        </div>

        <div class="tabs">
            <div class="tab-buttons">
                <button class="tab-button active" onclick="switchTab('monitor')">📈 Monitor</button>
                <button class="tab-button" onclick="switchTab('config')">⚙️ Configuration</button>
                <button class="tab-button" onclick="switchTab('device')">🔧 Device Settings</button>
            </div>

            <!-- Monitor Tab -->
            <div id="tab-monitor" class="tab-content active">
                <div class="channel-grid" id="channelGrid">
                    <!-- Channel cards will be populated by JavaScript -->
                </div>
            </div>

            <!-- Configuration Tab -->
            <div id="tab-config" class="tab-content">
                <div id="channelConfigs"></div>
                <div class="button-group">
                    <button onclick="saveChannelConfig()">💾 Save Configuration</button>
                    <button onclick="resetToDefaults()">🔄 Reset to Defaults</button>
                </div>
                <div id="configMessage" class="message"></div>
            </div>

            <!-- Device Settings Tab -->
            <div id="tab-device" class="tab-content">
                <div class="config-section device-config">
                    <h3>Serial Port Configuration</h3>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Port</label>
                            <input type="text" id="devicePort" placeholder="COM7 or /dev/ttyUSB0">
                        </div>
                        <div class="form-group">
                            <label>Baudrate</label>
                            <select id="deviceBaudrate">
                                <option value="9600">9600</option>
                                <option value="19200">19200</option>
                                <option value="38400">38400</option>
                                <option value="57600">57600</option>
                                <option value="115200">115200</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Parity</label>
                            <select id="deviceParity">
                                <option value="N">None (N)</option>
                                <option value="E">Even (E)</option>
                                <option value="O">Odd (O)</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Slave ID</label>
                            <input type="number" id="deviceSlaveId" min="1" max="247" value="1">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Read Interval (seconds)</label>
                            <input type="number" id="readInterval" min="1" max="60" step="0.5" value="2">
                        </div>
                    </div>
                </div>
                <div class="button-group">
                    <button onclick="saveDeviceConfig()">💾 Save Device Settings</button>
                </div>
                <div id="deviceMessage" class="message"></div>
            </div>
        </div>

        <script>
        let currentConfig = null;

        function switchTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('active');
            });

            // Show selected tab
            document.getElementById('tab-' + tabName).classList.add('active');
            event.target.classList.add('active');
        }

        function updateStatus() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    const indicator = document.getElementById('deviceStatus');
                    const statusText = document.getElementById('deviceStatusText');

                    if (data.device_connected) {
                        indicator.className = 'status-indicator connected';
                        statusText.textContent = 'Connected';
                    } else {
                        indicator.className = 'status-indicator disconnected';
                        statusText.textContent = 'Disconnected';
                    }

                    document.getElementById('devicePort').textContent = data.device_port;
                    document.getElementById('readInterval').textContent = data.read_interval;

                    if (data.last_update) {
                        const dt = new Date(data.last_update);
                        document.getElementById('lastUpdate').textContent = dt.toLocaleTimeString();
                    }
                });
        }

        function updateChannelData() {
            fetch('/api/channels')
                .then(r => r.json())
                .then(data => {
                    const grid = document.getElementById('channelGrid');
                    grid.innerHTML = '';

                    const channels = data.channels;
                    for (const chId in channels) {
                        const ch = channels[chId];

                        const card = document.createElement('div');
                        card.className = 'channel-card ' + (ch.enabled ? 'enabled' : 'disabled');

                        card.innerHTML = `
                            <div class="channel-header">
                                <div>
                                    <div class="channel-name">${ch.name}</div>
                                    <div class="channel-id">Channel ${ch.id}</div>
                                </div>
                                <div>${ch.enabled ? '✓' : '✗'}</div>
                            </div>
                            <div class="channel-value">
                                ${ch.value !== null ? ch.value : '--'} ${ch.unit}
                            </div>
                            <div class="channel-raw">
                                Raw: ${ch.raw_ma} mA (${ch.raw_ua} µA)<br>
                                Range: ${ch.min_range} - ${ch.max_range} ${ch.unit}
                            </div>
                        `;

                        grid.appendChild(card);
                    }
                });
        }

        function loadConfig() {
            fetch('/api/config')
                .then(r => r.json())
                .then(config => {
                    currentConfig = config;

                    // Update device settings tab
                    document.getElementById('devicePort').value = config.device.port;
                    document.getElementById('deviceBaudrate').value = config.device.baudrate;
                    document.getElementById('deviceParity').value = config.device.parity;
                    document.getElementById('deviceSlaveId').value = config.device.slave_id;
                    document.getElementById('readInterval').value = config.read_interval;

                    // Update channel configuration tab
                    const container = document.getElementById('channelConfigs');
                    container.innerHTML = '';

                    config.channels.forEach((ch, idx) => {
                        const section = document.createElement('div');
                        section.className = 'config-section';
                        section.innerHTML = `
                            <h3>Channel ${ch.id} Configuration</h3>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Enabled</label>
                                    <input type="checkbox" id="ch${idx}_enabled" ${ch.enabled ? 'checked' : ''}>
                                </div>
                                <div class="form-group">
                                    <label>Channel Name</label>
                                    <input type="text" id="ch${idx}_name" value="${ch.name}">
                                </div>
                                <div class="form-group">
                                    <label>Min Value (at 4mA)</label>
                                    <input type="number" id="ch${idx}_min" value="${ch.min_value}" step="0.01">
                                </div>
                                <div class="form-group">
                                    <label>Max Value (at 20mA)</label>
                                    <input type="number" id="ch${idx}_max" value="${ch.max_value}" step="0.01">
                                </div>
                                <div class="form-group">
                                    <label>Unit</label>
                                    <input type="text" id="ch${idx}_unit" value="${ch.unit}">
                                </div>
                                <div class="form-group">
                                    <label>Decimals</label>
                                    <input type="number" id="ch${idx}_decimals" value="${ch.decimals}" min="0" max="6">
                                </div>
                            </div>
                        `;
                        container.appendChild(section);
                    });
                });
        }

        function saveChannelConfig() {
            const config = JSON.parse(JSON.stringify(currentConfig));

            config.channels.forEach((ch, idx) => {
                ch.enabled = document.getElementById(`ch${idx}_enabled`).checked;
                ch.name = document.getElementById(`ch${idx}_name`).value;
                ch.min_value = parseFloat(document.getElementById(`ch${idx}_min`).value);
                ch.max_value = parseFloat(document.getElementById(`ch${idx}_max`).value);
                ch.unit = document.getElementById(`ch${idx}_unit`).value;
                ch.decimals = parseInt(document.getElementById(`ch${idx}_decimals`).value);
            });

            fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(config)
            })
            .then(r => r.json())
            .then(data => {
                showMessage('configMessage', data.status === 'success', data.message);
                if (data.status === 'success') {
                    currentConfig = config;
                }
            });
        }

        function saveDeviceConfig() {
            const config = JSON.parse(JSON.stringify(currentConfig));

            config.device.port = document.getElementById('devicePort').value;
            config.device.baudrate = parseInt(document.getElementById('deviceBaudrate').value);
            config.device.parity = document.getElementById('deviceParity').value;
            config.device.slave_id = parseInt(document.getElementById('deviceSlaveId').value);
            config.read_interval = parseFloat(document.getElementById('readInterval').value);

            fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(config)
            })
            .then(r => r.json())
            .then(data => {
                showMessage('deviceMessage', data.status === 'success',
                    data.message + ' (restart server to apply changes)');
                if (data.status === 'success') {
                    currentConfig = config;
                }
            });
        }

        function resetToDefaults() {
            if (confirm('Reset all channels to default configuration?')) {
                fetch('/api/config')
                    .then(r => r.json())
                    .then(config => {
                        // This would need a server endpoint to reset to defaults
                        // For now, just reload
                        location.reload();
                    });
            }
        }

        function showMessage(elementId, success, message) {
            const el = document.getElementById(elementId);
            el.className = 'message ' + (success ? 'success' : 'error');
            el.textContent = message;
            el.style.display = 'block';
            setTimeout(() => { el.style.display = 'none'; }, 5000);
        }

        // Initialize
        loadConfig();
        updateStatus();
        updateChannelData();

        // Auto-refresh every 2 seconds
        setInterval(() => {
            updateStatus();
            updateChannelData();
        }, 2000);
        </script>
    </body>
    </html>
    """

    return render_template_string(template)


if __name__ == '__main__':
    print("\n" + "="*80)
    print("📊 Waveshare Analog Acquisition Server")
    print("="*80)

    config = load_config()
    print(f"Device Port: {config['device']['port']}")
    print(f"Baudrate: {config['device']['baudrate']}")
    print(f"Slave ID: {config['device']['slave_id']}")
    print(f"Read Interval: {config['read_interval']}s")
    print(f"\n🌐 Web UI: http://localhost:8000")
    print(f"📡 API Endpoints:")
    print(f"   GET  /api/channels - Get all channels")
    print(f"   GET  /api/channel/<id> - Get specific channel")
    print(f"   GET  /api/config - Get configuration")
    print(f"   POST /api/config - Save configuration")
    print(f"   GET  /api/status - Get server status")
    print("="*80 + "\n")

    # Start background data reader thread
    reader = threading.Thread(target=data_reader_thread, daemon=True)
    reader.start()

    # Start Flask server
    app.run(host='0.0.0.0', port=8000, debug=False)
