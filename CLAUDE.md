# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Flask-based sensor datalogger application that:
- Fetches sensor data from HTML pages (via HTTP or local file://)
- Encrypts payloads using AES-256 and signs with RSA
- Transmits to ODAMS/CPCB servers with retry logic
- Runs 24/7 on Raspberry Pi with systemd integration
- Provides a web admin interface for configuration and monitoring

## Common Commands

### Development
```bash
# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment variables
# Edit .env file with your credentials

# Run application (development)
python datalogger_app.py

# Access web UI
# http://localhost:9999 (credentials: admin/admin123)

# Run test server for local testing
python test_server.py
# Configure endpoint in .env to: http://localhost:5000/v1.0/industry/data
```

### Production (Raspberry Pi)
```bash
# Install as systemd service
sudo cp datalogger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable datalogger
sudo systemctl start datalogger

# View logs
sudo journalctl -u datalogger -f
# or
tail -f datalogger.log

# Service management
sudo systemctl status datalogger
sudo systemctl restart datalogger
sudo systemctl stop datalogger
```

## Architecture

### Threading Model
The application runs three concurrent threads:
1. **Main Thread**: Flask web server (port 9999) for admin interface
2. **Logger Thread** ([modules/threads.py:45](modules/threads.py#L45)): Background data collection and transmission
   - Always uses 15-minute aligned intervals
   - Timestamps aligned to XX:00, XX:15, XX:30, XX:45
3. **Heartbeat Thread** ([modules/threads.py:20](modules/threads.py#L20)): IP reporting every 30 minutes

### Module Structure

```
modules/
├── config.py        # Environment config (.env) and sensor config (sensors.json) management
├── status.py        # In-memory status tracking (no file persistence)
├── threads.py       # Background threads (logger_thread, heartbeat_thread)
├── network.py       # Data fetching, server transmission, error reporting
├── crypto.py        # AES encryption + RSA signature generation
├── payload.py       # JSON payload construction
├── queue.py         # Failed transmission queue with retry logic
├── utils.py         # Timestamp alignment utilities
├── routes.py        # Flask web routes (/health, /test_fetch, /test_send)
└── constants.py     # Shared constants, logging setup
```

### Configuration Architecture

The application uses a three-tier configuration system:

#### 1. Environment Variables (.env) - Static Constants
Loaded once at startup, immutable during runtime:
- `TOKEN_ID` - AES encryption key (base64 encoded)
- `DEVICE_ID` - Unique device identifier
- `STATION_ID` - Station identifier
- `PUBLIC_KEY` - RSA public key (PEM format)
- `DATAPAGE_URL` - Source URL for sensor data
- `ENDPOINT` - ODAMS/CPCB server endpoint
- `ERROR_ENDPOINT_URL` - Error reporting endpoint
- `ERROR_SESSION_COOKIE` - Session cookie for error reporting

**Important**: Changes to .env require application restart. Values are read-only in web UI.

#### 2. Sensor Configuration (sensors.json) - Runtime Config
Editable via web UI, reloaded on each logger cycle:
```json
{
  "server_running": false,
  "sensors": [
    {"sensor_id": "S01", "param_name": "bod", "unit": "mg/L"}
  ]
}
```

#### 3. In-Memory Status - Runtime Statistics
Not persisted to disk, resets on restart:
- `last_fetch_success` - Last successful data fetch timestamp
- `last_send_success` - Last successful transmission timestamp
- `total_sends` - Total transmission attempts
- `failed_sends` - Failed transmission count
- `last_error` - Most recent error message

See [modules/status.py](modules/status.py) for implementation.

### Data Flow

1. **Fetch**: HTML page is fetched and parsed (BeautifulSoup) to extract sensor values from `<tr>` tags with specific IDs (`SID`, `MVAL`, `MUNIT`)
2. **Build**: Plain JSON payload is constructed with sensor data and aligned timestamps
3. **Encrypt**: Payload is encrypted with AES-256 (ECB mode), key derived from SHA256(token_id)
4. **Sign**: RSA signature generated using `{token_id}$*{timestamp}` encrypted with public key
5. **Send**: POST to endpoint with encrypted payload, X-Device-Id header, and signature
6. **Retry**: On failure, payload is queued and retried after next successful send

### Logging Behavior

**15-Minute Aligned Intervals** (always enabled):
- Data sent at XX:00, XX:15, XX:30, XX:45
- Timestamps aligned to 15-min boundaries via [get_aligned_timestamp_ms()](modules/utils.py#L5)
- Flag: "U" (upload)
- Failed sends queued for retry

**Note**: Calibration mode has been removed. All logging uses 15-minute intervals.

### Error Reporting

Errors are automatically sent to error_endpoint_url with:
- Tag (FETCH_ERROR, SEND_FAILED, SERVER_ERROR, HEARTBEAT)
- Error message
- Context (device_id, station_id, public_ip, last_fetch/send times)
- Response data (if applicable)

See [send_error_to_endpoint()](modules/network.py#L25) for implementation.

### Queue Management

Failed transmissions are stored in [failed_queue.json](failed_queue.json):
- Max 100 items kept (oldest discarded)
- 7-day backdate limit enforced
- Retried after successful send ([retry_failed_transmissions()](modules/queue.py#L34))
- Signature regenerated for each retry attempt

### Timestamp Rules

- **Alignment**: Timestamps always align to 15-min boundaries (XX:00, XX:15, XX:30, XX:45)
- **Backdate Limit**: Server rejects data older than 7 days
- **Future Dates**: Not allowed
- **Timezone**: All times in IST (Asia/Kolkata)

See [validate_timestamp()](modules/utils.py#L66) for validation logic.

### HTML Parsing

Data page must have this structure:
```html
<tr class="EvenRow"> or <tr class="OddRow">
  <td id="SID1">S01</td>          <!-- sensor_id -->
  <td id="MVAL1">12.5</td>        <!-- value -->
  <td id="MUNIT1">mg/L</td>       <!-- unit -->
</tr>
```

Parser extracts data by matching sensor_id from sensors.json to SID*, then reading corresponding MVAL* and MUNIT* values. See [fetch_sensor_data()](modules/network.py#L151).

## Testing

Use [test_server.py](test_server.py) to verify encryption/decryption locally:
1. Run: `python test_server.py` (starts on port 5000)
2. Configure ENDPOINT in .env to `http://localhost:5000/v1.0/industry/data`
3. Restart application
4. Use "Test Fetch" and "Test Send" buttons in web UI
5. Check test server console for decrypted payload

## Key Implementation Details

- **No File Locking**: Removed - .env is read-only, sensors.json has minimal contention
- **No Config Reloading**: Environment variables loaded once at startup
- **In-Memory Status**: Status tracking doesn't write to disk, improving performance
- **Retry Logic**: 3 attempts with exponential backoff (1s, 2s, 4s) for server errors (5xx)
- **No Retry**: Client errors (4xx) are not retried
- **Signature Timestamp**: Uses format `%Y-%m-%d %H:%M:%S.%f` (milliseconds) for RSA signature
- **Logging**: Rotating file handler (10MB max, 5 backups) at [datalogger.log](datalogger.log)
- **Web Auth**: HTTP Basic Auth (admin/admin123 by default)
- **Health Endpoint**: GET /health returns JSON with system status

## Migration from Old Config

If upgrading from the old config.json system:
```bash
# Run migration script
python migrate_config.py

# This will:
# 1. Read existing config.json
# 2. Generate .env file
# 3. Generate sensors.json file
# 4. Back up old config.json
```

## Web UI

The web interface ([modules/routes.py](modules/routes.py)) displays:
- **Read-Only Section**: Environment variables from .env (disabled inputs)
- **Editable Section**: Sensors and server_running toggle from sensors.json
- **Status Display**: In-memory statistics (resets on restart)

**Note**: To change .env values, edit the file manually and restart the application.
