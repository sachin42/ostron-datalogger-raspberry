import os
from flask import request, render_template, redirect, jsonify, send_from_directory, flash, url_for

from .constants import logger
from .config import load_env_config, load_sensors_config, save_sensors_config, validate_sensors_config
from .status import status
from .queue import load_queue
from .network import fetch_sensor_data, fetch_all_sensors, send_to_server


def register_routes(app, auth):
    """Register all Flask routes"""

    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(os.path.join(app.root_path, 'static'),
                                   'favicon.ico', mimetype='image/vnd.microsoft.icon')

    # ========== Main Pages ==========

    @app.route('/')
    @auth.login_required
    def index():
        """Redirect to dashboard"""
        return redirect(url_for('dashboard'))

    @app.route('/dashboard')
    @auth.login_required
    def dashboard():
        """Main dashboard page"""
        sensors_config = load_sensors_config()
        status_dict = status.to_dict()

        # Exclude disabled ADS1115 channels from dashboard
        all_sensors = sensors_config.get('sensors', [])
        visible_sensors = [
            s for s in all_sensors
            if not (s.get('type') == 'ads1115' and not s.get('enabled', False))
        ]

        return render_template('dashboard.html',
                             config=sensors_config,
                             sensors=visible_sensors,
                             status=status_dict)

    @app.route('/sensors')
    @auth.login_required
    def sensors_page():
        """Sensors configuration page"""
        env_config = load_env_config()
        sensors_config = load_sensors_config()

        # Build a 4-element list for ADS1115 channels (one per channel, with defaults)
        all_sensors = sensors_config.get('sensors', [])
        ads_by_ch = {s['channel']: s for s in all_sensors if s.get('type') == 'ads1115'}
        ads1115_channels = [
            ads_by_ch.get(ch, {
                'channel': ch, 'enabled': False, 'param_name': '', 'unit': '',
                'scale_method': 'range', 'min_value': 0.0, 'max_value': 100.0, 'factor': 1.0
            })
            for ch in range(4)
        ]

        return render_template('sensors.html',
                             env_config=env_config,
                             sensors=all_sensors,
                             rtu_device=sensors_config.get('rtu_device'),
                             ads1115_channels=ads1115_channels)

    @app.route('/settings')
    @auth.login_required
    def settings_page():
        """Settings page (read-only env config)"""
        env_config = load_env_config()

        return render_template('settings.html',
                             env_config=env_config)

    # ========== API Endpoints ==========

    @app.route('/health')
    def health():
        """Health check endpoint (public)"""
        sensors_config = load_sensors_config()
        queue = load_queue()
        status_dict = status.to_dict()

        health_status = {
            "status": "running" if sensors_config.get('server_running') else "stopped",
            "last_fetch": status_dict.get('last_fetch_success', 'Never'),
            "last_send": status_dict.get('last_send_success', 'Never'),
            "total_sends": status_dict.get('total_sends', 0),
            "failed_sends": status_dict.get('failed_sends', 0),
            "queued_items": len(queue),
            "last_error": status_dict.get('last_error', ''),
            "config_valid": validate_sensors_config(sensors_config)[0]
        }

        return jsonify(health_status)

    @app.route('/api/sensor_data')
    @auth.login_required
    def api_sensor_data():
        """Get current sensor data"""
        try:
            sensors_config = load_sensors_config()
            sensors = fetch_all_sensors(sensors_config)

            return jsonify({
                "success": True,
                "sensors": sensors,
                "timestamp": status.to_dict().get('last_fetch_success', '')
            })
        except Exception as e:
            logger.error(f"API sensor_data error: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route('/api/toggle_server', methods=['POST'])
    @auth.login_required
    def api_toggle_server():
        """Toggle server running state"""
        try:
            sensors_config = load_sensors_config()
            sensors_config['server_running'] = not sensors_config.get('server_running', False)
            save_sensors_config(sensors_config)

            return jsonify({
                "success": True,
                "server_running": sensors_config['server_running']
            })
        except Exception as e:
            logger.error(f"API toggle_server error: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route('/api/save_sensors', methods=['POST'])
    @auth.login_required
    def api_save_sensors():
        """Save sensor configuration"""
        try:
            data = request.get_json()
            sensors = data.get('sensors', [])
            rtu_device = data.get('rtu_device')

            sensors_config = load_sensors_config()
            sensors_config['sensors'] = sensors
            sensors_config['rtu_device'] = rtu_device  # Save RTU device config

            # Validate configuration
            valid, msg = validate_sensors_config(sensors_config)
            if not valid:
                return jsonify({
                    "success": False,
                    "error": msg
                }), 400

            save_sensors_config(sensors_config)

            return jsonify({
                "success": True,
                "message": "Sensors saved successfully"
            })
        except Exception as e:
            logger.error(f"API save_sensors error: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route('/test_fetch')
    @auth.login_required
    def test_fetch():
        """Manual test of data fetching"""
        try:
            sensors_config = load_sensors_config()
            sensors = fetch_all_sensors(sensors_config)

            if not sensors:
                return jsonify({
                    "success": False,
                    "error": "No sensor data fetched. Check sensor configuration."
                })

            expected_count = len(sensors_config.get('sensors', []))
            return jsonify({
                "success": True,
                "sensors": sensors,
                "expected_count": expected_count,
                "actual_count": len(sensors)
            })
        except Exception as e:
            logger.error(f"Test fetch error: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route('/test_send')
    @auth.login_required
    def test_send():
        """Manual test of data sending"""
        try:
            sensors_config = load_sensors_config()
            sensors = fetch_all_sensors(sensors_config)

            if not sensors:
                return jsonify({
                    "success": False,
                    "error": "No sensor data fetched"
                })

            success, status_code, text, should_queue = send_to_server(sensors)

            return jsonify({
                "success": success,
                "status": status_code,
                "response": text,
                "should_queue": should_queue,
                "sensors": sensors
            })
        except Exception as e:
            logger.error(f"Test send error: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
