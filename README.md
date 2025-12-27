# 🚀 Datalogger: Sensor Data Collection & Transmission System

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Build Status](https://img.shields.io/github/actions/workflow/status/your-repo/ci.yml)](https://github.com/your-repo/actions)

A robust, modular Flask-based application for collecting sensor data from HTML sources, encrypting it (AES + RSA), and securely transmitting to ODAMS/CPCB servers. Designed for 24/7 operation on Raspberry Pi with systemd integration. Features background logging, retry logic, and a web admin interface.

## 📋 Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## ✨ Features
- 🔐 **Secure Encryption**: AES-256 encryption for payloads, RSA signatures for integrity.
- 🌐 **Web Interface**: Intuitive admin panel for configuration and monitoring.
- 🔄 **Reliable Transmission**: 3-attempt retries with exponential backoff; queues failed sends.
- ⏰ **Scheduled Logging**: 15-minute intervals (or 1-min calibration mode) for compliance. Calibration mode uses real-time timestamps and skips queuing failed sends.
- 📊 **Health Monitoring**: Real-time status via `/health` endpoint.
- 🛠️ **Raspberry Pi Optimized**: Cross-platform file locking, systemd service support.
- 📈 **Error Reporting**: Automated alerts to remote endpoints with context.

## 🛠️ Installation

### Prerequisites
- 🐍 Python 3.7+ (pre-installed on Raspberry Pi OS)
- 📦 pip (package manager)
- 🌐 Internet connection for data transmission
- 💾 Raspberry Pi (recommended: 4GB RAM, SD card with 16GB+)

### Step-by-Step Installation on Raspberry Pi

1. **Update System**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install Python and Dependencies**:
   ```bash
   sudo apt install python3 python3-pip python3-venv -y
   ```

3. **Clone Repository**:
   ```bash
   git clone https://github.com/your-repo/datalogger.git
   cd datalogger
   ```

4. **Create Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Configure Application**:
   - Edit `config.json` with your settings (see [Configuration](#configuration)).
   - Run initial setup: `python datalogger_app.py` (access web UI at http://localhost:9999).

6. **Install as Systemd Service** (for auto-start):
   ```bash
   sudo cp datalogger.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable datalogger
   sudo systemctl start datalogger
   ```
   - Logs: `sudo journalctl -u datalogger -f`

7. **Verify Installation**:
   - Check health: `curl http://localhost:9999/health`
   - Access web UI in browser.

### Docker Installation (Alternative)
```bash
docker build -t datalogger .
docker run -p 9999:9999 datalogger
```

## 🚀 Quick Start
1. 🏃‍♂️ Start the app: `python datalogger_app.py`
2. 🌐 Open http://localhost:9999 in browser.
3. 🔑 Login with `admin`/`admin123` (change immediately!).
4. ⚙️ Configure sensors, URLs, and credentials.
5. ✅ Test fetch/send via UI buttons (use `python test_server.py` for local testing).
6. 🔄 Monitor status dashboard.

## ⚙️ Configuration
Edit `config.json`:
```json
{
  "token_id": "your-token",
  "device_id": "device-123",
  "station_id": "station-456",
  "public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
  "datapage_url": "http://sensor-page.com",
  "sensors": [{"sensor_id": "TEMP", "param_name": "temperature", "unit": "°C"}],
  "calibration_mode": false,
  "server_running": true
}
```
- 📝 **Fields**: `token_id` (encryption key), `datapage_url` (HTML source), `endpoint` (server URL), sensors array, `calibration_mode` (enables 1-min intervals and 'C' flag).
- 🔄 Reload config via web UI or restart app.

## 📖 Usage
- **Web Admin**: Configure settings, view status, test operations.
- **Background Logging**: Runs automatically; monitors every 15 minutes.
- **Manual Tests**: Use `/test_fetch` and `/test_send` endpoints.
- **Logs**: View in `datalogger.log` or systemd journal.

### Example Workflow
1. 📡 Fetch data from HTML page.
2. 🔒 Encrypt payload with AES + sign with RSA (flag: 'U' normal, 'C' calibration; timestamps: aligned in normal, real-time in calibration).
3. 📤 Send to ODAMS server.
4. ❌ On failure: Queue for retry on next success (not in calibration mode).

### Testing
Run `python test_server.py` to start a local test server on port 5000. Configure the `endpoint` in the web UI to `http://localhost:5000/v1.0/industry/data` for testing with your credentials. The test server decrypts and logs payloads for verification.

## 🔗 API Endpoints
- `GET /`: Admin dashboard.
- `GET /health`: System status (JSON).
- `GET /test_fetch`: Manual data fetch (requires auth).
- `GET /test_send`: Manual data send (requires auth).
- `GET /favicon.ico`: App icon.

All protected by HTTP Basic Auth.

## 🐛 Troubleshooting
- **Common Issues**:
  - ❌ Fetch fails: Check `datapage_url` accessibility.
  - 🚫 Send errors: Verify token/key; check server response in logs.
  - 🕒 Timezone issues: Ensure IST alignment.
- **Logs**: `tail -f datalogger.log`
- **Reset Config**: Delete `config.json` and restart.
- **Debug Mode**: Set `DEBUG=1` in environment.
- 📞 For help, see [Support](#support).

## 🤝 Contributing
1. 🍴 Fork the repo.
2. 🌿 Create a branch: `git checkout -b feature/new-feature`.
3. 🧪 Add tests and run `pytest`.
4. 📝 Commit: `git commit -m 'Add new feature'`.
5. 🚀 Push and open PR.

Guidelines: Follow PEP8, add type hints, update docs.

## 📄 License
MIT License - see [LICENSE](LICENSE) for details.

## 📞 Support
- 📧 Issues: [GitHub Issues](https://github.com/your-repo/datalogger/issues)
- 📖 Docs: [AGENTS.md](AGENTS.md) (internal guidelines)
- 🆘 Community: Join discussions or contact maintainers.

---

Made with ❤️ for reliable sensor monitoring.