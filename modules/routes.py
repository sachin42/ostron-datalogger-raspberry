import os
from flask import request, render_template_string, redirect, jsonify, send_from_directory

from .constants import logger
from .config import load_config, save_config, validate_config
from .queue import load_queue
from .network import fetch_sensor_data, send_to_server


def register_routes(app, auth):
    """Register all Flask routes"""

    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(os.path.join(app.root_path, 'static'),
                                   'favicon.ico', mimetype='image/vnd.microsoft.icon')

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
    <div class="error-msg">Warning: Configuration incomplete: {{ config_msg }}</div>
    {% endif %}

    <div class="status-card">
        <h2>System Status</h2>
        <div class="status-grid">
            <div class="status-item {% if config.server_running %}status-good{% else %}status-bad{% endif %}">
                <label>Server Status</label>
                <div class="value">{{ 'Running' if config.server_running else 'Stopped' }}</div>
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
