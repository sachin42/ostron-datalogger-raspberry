# CPCB/ODAMS Environmental Datalogger

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

Enterprise-grade sensor data collection and transmission system for CPCB/ODAMS compliance monitoring. Supports multiple sensor protocols (IQ Web Connect, Modbus TCP, Modbus RTU), continuous data averaging, secure encryption (AES-256 + RSA), and automatic retry mechanisms. Designed for 24/7 operation on industrial hardware with comprehensive monitoring and diagnostics.

## 🎯 Key Features

### Multi-Protocol Sensor Support
- **IQ Web Connect**: HTML-based sensor data extraction via HTTP/file
- **Modbus TCP**: Network-based industrial sensor communication (Ethernet)
- **Modbus RTU**: Serial RS485/RS232 sensor communication
- Support for mixed sensor configurations

### Data Quality & Reliability
- **Continuous Sampling**: Automatic data collection every 10-30 seconds
- **Statistical Averaging**: Sends average of 6-30 samples per transmission
- **Noise Reduction**: Eliminates momentary spikes and measurement errors
- **Thread-Safe Architecture**: Independent data collection and transmission threads

### Security & Compliance
- **AES-256 Encryption**: Military-grade payload encryption
- **RSA Digital Signatures**: Cryptographic integrity verification
- **Aligned Timestamps**: Regulatory-compliant 15-minute interval reporting
- **Audit Trail**: Comprehensive logging with rotating file handlers

### Transmission & Recovery
- **Smart Retry Logic**: Exponential backoff with configurable attempts
- **Persistent Queue**: Failed transmissions stored for automatic retry
- **Error Reporting**: Automated alerts to monitoring endpoints
- **Heartbeat Monitoring**: System health updates every 30 minutes

### Enterprise Features
- **Web Management Interface**: Real-time monitoring and configuration
- **RESTful API**: Programmatic access to system status
- **Development Mode**: Accelerated testing with 1-minute intervals
- **Systemd Integration**: Auto-start and watchdog on Linux systems
- **Production-Ready**: Tested for continuous operation on Raspberry Pi

## 📋 Table of Contents

- [Architecture](#architecture)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Sensor Configuration](#sensor-configuration)
- [Operation](#operation)
- [Monitoring & Diagnostics](#monitoring--diagnostics)
- [Troubleshooting](#troubleshooting)
- [Production Deployment](#production-deployment)
- [API Reference](#api-reference)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## 🏗 Architecture

### Threading Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Flask Web Server (Port 9999)             │
│                     Configuration & Monitoring               │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼──────┐    ┌────────▼────────┐   ┌───────▼────────┐
│ Data Collect │    │ Logger Thread   │   │ Heartbeat      │
│ Every 10-30s │    │ Send Every 1-15m│   │ Every 30min    │
│              │    │                 │   │                │
│ IQ Web       │    │ Calculate Avg   │   │ Health Check   │
│ Modbus TCP   │────▶ Send to Server  │   │ IP Reporting   │
│ Modbus RTU   │    │ Queue on Fail   │   │                │
└──────────────┘    └─────────────────┘   └────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Retry Queue       │
                    │  Background Worker │
                    │  (Auto-triggered)  │
                    └────────────────────┘
```

### Data Flow

1. **Collection**: Sensors sampled every 10-30 seconds (configurable)
2. **Aggregation**: Readings stored in memory for statistical averaging
3. **Processing**: Average calculated at aligned intervals (1 or 15 minutes)
4. **Encryption**: AES-256 payload encryption + RSA signature generation
5. **Transmission**: HTTPS POST to ODAMS/CPCB endpoint
6. **Recovery**: Failed transmissions queued and retried automatically

### Supported Sensor Protocols

| Protocol | Transport | Use Case | Max Devices |
|----------|-----------|----------|-------------|
| IQ Web Connect | HTTP/Local | Web-based sensors | Unlimited |
| Modbus TCP | Ethernet | PLCs, RTUs | Unlimited |
| Modbus RTU | RS485/Serial | Industrial sensors | 32 per bus |

## 💻 System Requirements

### Hardware
- **Minimum**: Raspberry Pi 3B+ (1GB RAM, 8GB SD card)
- **Recommended**: Raspberry Pi 4 (2GB+ RAM, 16GB+ SD card)
- **Network**: Ethernet connection (required for Modbus TCP)
- **Serial**: USB-to-RS485 adapter (required for Modbus RTU)

### Software
- **OS**: Raspberry Pi OS (Debian 10+) or Ubuntu 18.04+
- **Python**: 3.7 or higher
- **Disk Space**: 500MB minimum (including logs)
- **Network**: Internet access for ODAMS transmission

### Dependencies
```
Flask==3.0.0
flask-httpauth==4.8.0
requests==2.31.0
beautifulsoup4==4.12.2
pycryptodome==3.19.0
pytz==2023.3
python-dotenv==1.0.0
pymodbus==3.5.4
pyserial==3.5
```

## 🚀 Installation

### Quick Start (Raspberry Pi)

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install Python and dependencies
sudo apt install python3 python3-pip python3-venv git -y

# 3. Clone repository
cd /opt
sudo git clone https://github.com/your-org/datalogger.git
cd datalogger

# 4. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 5. Install Python packages
pip install -r requirements.txt

# 6. Configure application
cp .env.example .env
nano .env  # Edit with your credentials

# 7. Test installation
python datalogger_app.py
# Access web UI at http://<raspberry-pi-ip>:9999
# Default credentials: admin / admin123

# 8. Install as systemd service (see Production Deployment section)
```

### Docker Installation (Alternative)

```bash
# Build image
docker build -t datalogger:latest .

# Run container
docker run -d \
  --name datalogger \
  --restart unless-stopped \
  -p 9999:9999 \
  -v $(pwd)/.env:/app/.env:ro \
  -v $(pwd)/sensors.json:/app/sensors.json \
  -v $(pwd)/logs:/app/logs \
  datalogger:latest
```

## ⚙️ Configuration

### Environment Variables (.env)

Create a `.env` file in the project root with the following configuration:

```bash
# Encryption & Authentication
TOKEN_ID=Hvg_LrxeePXexh7TM76jQqWsWGRV4M4gvX1_tvKDMN4=
DEVICE_ID=device_7025
STATION_ID=station_8203
UID=861192078519884

# RSA Public Key (PEM format - use literal \n in string)
PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqh...\n-----END PUBLIC KEY-----"

# ODAMS/CPCB Endpoints
ENDPOINT=https://cems.cpcb.gov.in/v1.0/industry/data
ERROR_ENDPOINT_URL=http://65.1.87.62/ocms/Cpcb/add_cpcberror
ERROR_SESSION_COOKIE=e1j7mnclaennlc5vqfr8ms2iiv1ng2i7

# Data Source (IQ Web Connect)
DATAPAGE_URL=http://192.168.1.100/datapage.html
# Or use local file: file:///path/to/datapage.html

# Development Mode (optional)
DEV_MODE=false  # Set to 'true' for 1-minute testing intervals
```

**Configuration Notes:**
- All `.env` changes require application restart
- `TOKEN_ID`: Base64-encoded AES encryption key (32 bytes)
- `PUBLIC_KEY`: RSA public key for signature generation
- `DEV_MODE=true`: Use for testing (1-min intervals, 10s sampling)
- `DEV_MODE=false`: Production mode (15-min intervals, 30s sampling)

### Sensor Configuration (sensors.json)

The `sensors.json` file defines your sensor configuration and is editable via the web UI:

```json
{
  "server_running": true,
  "sensors": [
    {
      "type": "iq_web_connect",
      "sensor_id": "S01",
      "param_name": "ph",
      "unit": "pH"
    },
    {
      "type": "modbus_tcp",
      "ip": "192.168.1.100",
      "port": 502,
      "slave_id": 1,
      "register_type": "holding",
      "register_address": 100,
      "data_type": "float32",
      "byte_order": "big",
      "word_order": "big",
      "param_name": "temperature",
      "unit": "°C"
    }
  ],
  "rtu_device": {
    "port": "COM7",
    "baudrate": 9600,
    "parity": "N",
    "bytesize": 8,
    "stopbits": 1,
    "timeout": 3
  }
}
```

**Configuration is automatically reloaded** on each data collection cycle - no restart required.

## 🔧 Sensor Configuration

### IQ Web Connect Sensors

For HTML-based sensor pages (e.g., IQ SensorNet devices):

```json
{
  "type": "iq_web_connect",
  "sensor_id": "S01",
  "param_name": "bod",
  "unit": "mg/L"
}
```

**Requirements:**
- HTML page must have `<tr>` elements with `SID`, `MVAL`, `MUNIT` IDs
- Accessible via HTTP or `file://` URL

### Modbus TCP Sensors

For Ethernet-connected PLCs and RTUs:

```json
{
  "type": "modbus_tcp",
  "ip": "192.168.1.50",
  "port": 502,
  "slave_id": 1,
  "register_type": "holding",
  "register_address": 0,
  "data_type": "float32",
  "byte_order": "big",
  "word_order": "big",
  "param_name": "flow_rate",
  "unit": "m3/h"
}
```

**Supported Data Types:**
- 16-bit: `uint16`, `int16`, `uint8_high`, `uint8_low`, `int8_high`, `int8_low`
- 32-bit: `uint32`, `int32`, `float32`
- Register Types: Holding (FC3), Input (FC4), Coil (FC1), Discrete (FC2)

**Byte Order Options:**
- ABCD (big/big) - Standard Modbus
- DCBA (little/little) - Fully reversed
- BADC (little/big) - Byte swap
- CDAB (big/little) - Word swap

### Modbus RTU Sensors (RS485)

For serial-connected sensors (single bus, multiple devices):

**1. Configure RTU Device:**
```json
{
  "rtu_device": {
    "port": "COM7",          // Windows: COM7, Linux: /dev/ttyUSB0
    "baudrate": 9600,
    "parity": "N",           // N=None, E=Even, O=Odd
    "bytesize": 8,
    "stopbits": 1,
    "timeout": 3
  }
}
```

**2. Add RTU Sensors:**
```json
{
  "type": "modbus_rtu",
  "slave_id": 2,
  "register_type": "input",
  "register_address": 100,
  "data_type": "int16",
  "byte_order": "big",
  "param_name": "pressure",
  "unit": "bar"
}
```

**Important Notes:**
- Only one RTU device (serial port) supported
- Multiple sensors per bus (unique slave IDs)
- Linux: Grant serial port permissions (`sudo usermod -a -G dialout $USER`)
- Check device compatibility (9600 8N1 is most common)

For detailed Modbus configuration examples, see [MODBUS_TCP_GUIDE.md](MODBUS_TCP_GUIDE.md).

## 🎮 Operation

### Starting the Application

**Development/Testing:**
```bash
source .venv/bin/activate
python datalogger_app.py
```

**Production (systemd service):**
```bash
sudo systemctl start datalogger
sudo systemctl status datalogger
```

### Web Interface

Access the admin interface at `http://<device-ip>:9999`

**Default Credentials:**
- Username: `admin`
- Password: `admin123`

⚠️ **Change these credentials immediately in production!**

### Web UI Features

1. **Dashboard** (`/dashboard`): Real-time sensor values and system status
2. **Sensors** (`/sensors`): Configure sensor parameters by protocol type
3. **Settings** (`/settings`): View environment configuration (read-only)
4. **Health** (`/health`): JSON API for system monitoring

**Manual Testing:**
- **Test Fetch**: Validate sensor data collection
- **Test Send**: Verify server transmission (check logs for decrypted payload)

### Operating Modes

| Mode | Sampling Interval | Send Interval | Samples/Send | Use Case |
|------|------------------|---------------|--------------|----------|
| **Production** | 30 seconds | 15 minutes | ~30 | Regulatory compliance |
| **Development** | 10 seconds | 1 minute | ~6 | Testing & commissioning |

Set mode in `.env`: `DEV_MODE=true` (dev) or `DEV_MODE=false` (prod)

## 📊 Monitoring & Diagnostics

### Log Files

**Application Logs:**
```bash
tail -f datalogger.log
```

**Systemd Logs:**
```bash
sudo journalctl -u datalogger -f
sudo journalctl -u datalogger --since "1 hour ago"
```

**Log Rotation:**
- Automatic rotation at 10MB file size
- Keeps last 5 backup files
- Location: `datalogger.log`, `datalogger.log.1`, etc.

### Health Check Endpoint

```bash
curl http://localhost:9999/health
```

**Response:**
```json
{
  "status": "healthy",
  "server_running": true,
  "uptime_seconds": 86400,
  "last_fetch_success": "2026-01-08T14:30:00+05:30",
  "last_send_success": "2026-01-08T14:30:00+05:30",
  "total_sends": 96,
  "failed_sends": 2,
  "queue_size": 0,
  "last_error": null
}
```

### Error Reporting

Errors are automatically sent to `ERROR_ENDPOINT_URL` with:
- Error type (FETCH_ERROR, SEND_FAILED, HEARTBEAT)
- Error message and stack trace
- Device context (ID, station, public IP)
- Last successful operation timestamps

## 🔍 Troubleshooting

### Common Issues

**1. Sensor Data Not Fetching**
```bash
# Check datapage accessibility
curl http://192.168.1.100/datapage.html

# Test fetch via UI
# Check logs: tail -f datalogger.log | grep FETCH
```

**Solution:**
- Verify `DATAPAGE_URL` in `.env`
- Check network connectivity
- For malformed HTTP responses, raw socket fallback is automatic

**2. Transmission Failures**
```bash
# Check endpoint connectivity
curl -X POST https://cems.cpcb.gov.in/v1.0/industry/data

# Review queue
cat failed_queue.json
```

**Solution:**
- Verify `TOKEN_ID` and `PUBLIC_KEY` in `.env`
- Check firewall rules (allow outbound HTTPS)
- Review server response in logs for API errors

**3. Modbus TCP Connection Issues**
```bash
# Test Modbus connectivity
pip install pymodbus
python -c "from pymodbus.client import ModbusTcpClient; c = ModbusTcpClient('192.168.1.100'); print(c.connect())"
```

**Solution:**
- Verify IP address and port (default: 502)
- Check firewall on PLC/RTU
- Use `modpoll` tool for diagnostics

**4. Modbus RTU Serial Port Errors**
```bash
# List serial ports
ls /dev/tty*

# Check permissions
ls -l /dev/ttyUSB0

# Add user to dialout group
sudo usermod -a -G dialout $USER
# Logout and login again
```

**Solution:**
- Verify correct COM port/device
- Check USB adapter drivers (CH340, FTDI)
- Ensure no other application is using the port
- Verify baud rate matches device (9600 is most common)

**5. Service Won't Start**
```bash
sudo systemctl status datalogger
sudo journalctl -u datalogger -n 50
```

**Solution:**
- Check Python syntax: `python -m py_compile datalogger_app.py`
- Verify `.env` file permissions and format
- Ensure virtual environment is properly configured in service file

### Debug Mode

Enable verbose logging:
```bash
# In modules/constants.py, change logger level:
logger.setLevel(logging.DEBUG)
```

### Reset Configuration

```bash
# Backup current config
cp sensors.json sensors.json.backup

# Reset to defaults
python datalogger_app.py  # Will create default sensors.json
```

## 🏭 Production Deployment

### Systemd Service Installation

**1. Create service file:**
```bash
sudo nano /etc/systemd/system/datalogger.service
```

**2. Service configuration:**
```ini
[Unit]
Description=CPCB/ODAMS Environmental Datalogger
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/datalogger
Environment="PATH=/opt/datalogger/.venv/bin"
ExecStart=/opt/datalogger/.venv/bin/python datalogger_app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Resource limits
LimitNOFILE=65536
TimeoutStartSec=30
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

**3. Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable datalogger
sudo systemctl start datalogger
sudo systemctl status datalogger
```

### Production Checklist

- [ ] Change default admin password
- [ ] Configure all sensors in `sensors.json`
- [ ] Set `DEV_MODE=false` in `.env`
- [ ] Test manual fetch and send operations
- [ ] Verify ODAMS connectivity and credentials
- [ ] Enable systemd service for auto-start
- [ ] Configure log monitoring (syslog forwarding)
- [ ] Set up backup for configuration files
- [ ] Document sensor locations and IDs
- [ ] Test recovery after power failure
- [ ] Verify queue functionality under network outage
- [ ] Configure firewall rules (allow port 502 for Modbus TCP)

### High Availability Setup

**Option 1: Dual Raspberry Pi (Active-Standby)**
- Primary device sends data continuously
- Standby device monitors primary via heartbeat
- Manual failover procedure documented

**Option 2: Load Balancer (Multiple Devices)**
- Multiple devices collect redundant data
- Load balancer at ODAMS endpoint
- Requires coordination to avoid duplicate transmissions

### Backup Strategy

```bash
# Automated daily backup script
#!/bin/bash
BACKUP_DIR="/opt/datalogger_backups"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR
cd /opt/datalogger

tar -czf $BACKUP_DIR/datalogger_$DATE.tar.gz \
  .env \
  sensors.json \
  failed_queue.json \
  datalogger.log

# Keep last 7 days
find $BACKUP_DIR -name "datalogger_*.tar.gz" -mtime +7 -delete
```

Add to crontab: `0 2 * * * /opt/datalogger/backup.sh`

## 📡 API Reference

### Health Check
```
GET /health
```
Returns system status and statistics.

### Manual Operations
```
GET /test_fetch
GET /test_send
```
Requires HTTP Basic Authentication.

### Sensor Data API
```
GET /api/sensor_data
```
Returns current averaged sensor readings.

**Response:**
```json
{
  "success": true,
  "sensors": {
    "ph": {"value": "7.2", "unit": "pH"},
    "temperature": {"value": "25.4", "unit": "°C"}
  },
  "timestamp": "2026-01-08T14:30:00+05:30"
}
```

### Configuration Management
```
POST /api/save_sensors
```
Update sensor configuration (requires auth).

**Request Body:**
```json
{
  "sensors": [...],
  "rtu_device": {...}
}
```

## 🛠 Development

### Development Setup

```bash
# Clone repository
git clone https://github.com/your-org/datalogger.git
cd datalogger

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies including dev tools
pip install -r requirements.txt
pip install pytest pytest-cov pylint black

# Run tests
pytest tests/

# Code formatting
black modules/

# Linting
pylint modules/
```

### Testing with Local Server

```bash
# Terminal 1: Start test server
python test_server.py

# Terminal 2: Configure datalogger
# Edit .env:
# ENDPOINT=http://localhost:5000/v1.0/industry/data
# ERROR_ENDPOINT_URL=http://localhost:5000/ocms/Cpcb/add_cpcberror

# Start datalogger
python datalogger_app.py
```

The test server provides:
- Web UI at http://localhost:5000
- Payload decryption and logging
- Simulated HTTP and ODAMS errors
- Real-time request inspection

### Project Structure

```
datalogger/
├── modules/
│   ├── config.py              # Configuration management
│   ├── constants.py           # Shared constants and logging
│   ├── crypto.py              # AES encryption + RSA signatures
│   ├── data_collector.py      # Data averaging system
│   ├── modbus_fetcher.py      # Modbus TCP implementation
│   ├── modbus_rtu_fetcher.py  # Modbus RTU implementation
│   ├── network.py             # HTTP/Modbus fetching & transmission
│   ├── payload.py             # JSON payload construction
│   ├── queue.py               # Failed transmission retry logic
│   ├── routes.py              # Flask web routes
│   ├── status.py              # In-memory status tracking
│   ├── threads.py             # Background worker threads
│   └── utils.py               # Timestamp utilities
├── templates/                 # Web UI templates
│   ├── base.html
│   ├── dashboard.html
│   ├── sensors.html
│   └── settings.html
├── static/                    # CSS and JavaScript
│   ├── css/style.css
│   └── js/main.js
├── tests/                     # Unit and integration tests
├── .env                       # Environment configuration (not in git)
├── sensors.json               # Sensor configuration
├── datalogger_app.py          # Main application entry point
├── test_server.py             # Local testing server
├── requirements.txt           # Python dependencies
├── datalogger.service         # Systemd service file
├── CLAUDE.md                  # Development documentation
├── MODBUS_TCP_GUIDE.md        # Modbus configuration guide
└── README.md                  # This file
```

### Code Style

- **Python**: PEP 8, type hints where applicable
- **Comments**: Docstrings for all public functions
- **Logging**: Use appropriate levels (DEBUG, INFO, WARNING, ERROR)
- **Error Handling**: Catch specific exceptions, log with context

### Testing Guidelines

```python
# Example test structure
def test_data_collector_averaging():
    collector = DataCollector()
    collector.add_reading('ph', 7.0)
    collector.add_reading('ph', 7.4)
    collector.add_reading('ph', 7.2)

    averages = collector.get_averages()
    assert averages['ph'] == pytest.approx(7.2, rel=0.01)
```

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/new-feature`
3. **Commit** changes: `git commit -m 'Add new feature'`
4. **Test** thoroughly: `pytest tests/`
5. **Push** to your fork: `git push origin feature/new-feature`
6. **Submit** a Pull Request

### Contribution Guidelines

- Follow existing code style and architecture
- Add unit tests for new features
- Update documentation (README, CLAUDE.md)
- Ensure all tests pass
- Keep commits focused and well-described

### Reporting Issues

When reporting bugs, please include:
- Python version and OS
- Full error message and stack trace
- Relevant log excerpts
- Configuration (sanitized, no credentials)
- Steps to reproduce

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

This software is provided "as is" without warranty. See license for full terms.

## 📞 Support & Resources

- **Documentation**: See [CLAUDE.md](CLAUDE.md) for architecture details
- **Modbus Guide**: See [MODBUS_TCP_GUIDE.md](MODBUS_TCP_GUIDE.md) for sensor configuration
- **Issues**: Report bugs at [GitHub Issues](https://github.com/your-org/datalogger/issues)
- **Email**: support@your-organization.com
- **Community**: Join discussions and get help

---

**Developed for reliable environmental monitoring and regulatory compliance.**

*Version 2.0 | Last Updated: January 2026*
