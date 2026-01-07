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

# For development/testing, enable DEV_MODE in .env for 1-minute intervals
# DEV_MODE=true  (1-minute intervals, faster testing)
# DEV_MODE=false (15-minute intervals, production)

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

The application uses a multi-threaded architecture with data averaging:

1. **Main Thread**: Flask web server (port 9999) for admin interface
2. **Data Collection Thread** ([modules/threads.py:20](modules/threads.py#L20)): Continuous sensor data sampling
   - Production mode (DEV_MODE=false): Fetches every 30 seconds
   - Development mode (DEV_MODE=true): Fetches every 10 seconds
   - Stores readings in memory for averaging
   - Runs independently from transmission schedule
3. **Logger Thread** ([modules/threads.py:88](modules/threads.py#L88)): Sends averaged data to server
   - Production mode (DEV_MODE=false): 15-minute aligned intervals (XX:00, XX:15, XX:30, XX:45)
   - Development mode (DEV_MODE=true): 1-minute aligned intervals (XX:00, XX:01, XX:02, ...)
   - Calculates average of collected samples and sends to server
   - Production: ~30 samples per send (30s × 30 = 15 minutes)
   - Development: ~6 samples per send (10s × 6 = 1 minute)
   - Clears collected data after sending
4. **Heartbeat Thread** ([modules/threads.py:66](modules/threads.py#L66)): IP reporting every 30 minutes
5. **Retry Queue Thread** ([modules/queue.py:40](modules/queue.py#L40)): Dynamic background worker (spawned as needed)
   - Triggered automatically after successful send
   - Processes failed queue in FIFO order
   - Stops on first error (4xx/5xx or network failure)
   - Removes items that get 200 response (even with wrong data)
   - Auto-exits when queue is empty or on error
   - Only one instance runs at a time (thread-safe)

### Module Structure

```
modules/
├── config.py            # Environment config (.env) and sensor config (sensors.json) management
├── status.py            # In-memory status tracking (no file persistence)
├── data_collector.py    # Data averaging - collects samples in memory for averaging
├── threads.py           # Background threads (data_collection, logger, heartbeat)
├── network.py           # Data fetching, server transmission, error reporting
├── crypto.py            # AES encryption + RSA signature generation
├── payload.py           # JSON payload construction
├── queue.py             # Failed transmission queue with retry logic
├── utils.py             # Timestamp alignment utilities
├── routes.py            # Flask web routes (/health, /test_fetch, /test_send)
├── modbus_fetcher.py    # Modbus TCP sensor data fetching
├── modbus_rtu_fetcher.py # Modbus RTU (RS485) sensor data fetching
└── constants.py         # Shared constants, logging setup
```

### Configuration Architecture

The application uses a three-tier configuration system:

#### 1. Environment Variables (.env) - Static Constants

Loaded once at startup, immutable during runtime:
- `TOKEN_ID` - AES encryption key (base64 encoded)
- `DEVICE_ID` - Unique device identifier
- `STATION_ID` - Station identifier
- `UID` - Unique identifier for error reporting
- `PUBLIC_KEY` - RSA public key (PEM format)
- `DEV_MODE` - Development mode flag (true/false)
  - `true` = 1-minute intervals for faster testing
  - `false` = 15-minute intervals for production
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

### Data Averaging System

The datalogger uses a continuous sampling and averaging approach to provide more stable and representative sensor readings:

#### Sampling Intervals

- **Production Mode** (DEV_MODE=false): Fetches sensor data every **30 seconds**
- **Development Mode** (DEV_MODE=true): Fetches sensor data every **10 seconds**

#### How It Works

1. **Data Collection Thread** continuously fetches sensor data at the configured interval
2. Each reading is stored in memory in [modules/data_collector.py](modules/data_collector.py)
3. When it's time to send data (1-minute or 15-minute aligned), the **Logger Thread**:
   - Calculates the average of all collected samples for each sensor
   - Rounds the average to 2 decimal places
   - Sends the averaged data to the server
   - Clears the collected samples

#### Sample Counts

- **Production**: ~30 samples per transmission (30 seconds × 30 = 15 minutes)
- **Development**: ~6 samples per transmission (10 seconds × 6 = 1 minute)

#### Benefits

- **Noise reduction**: Smooths out momentary spikes or dips in sensor readings
- **More representative data**: Averages capture the true state over the interval
- **Independent threads**: Data collection continues even if transmission fails
- **No data loss**: If transmission fails, samples are still being collected for next send

#### Implementation Details

See [modules/data_collector.py](modules/data_collector.py) for the `DataCollector` class that manages:
- Thread-safe reading storage with locks
- Average calculation
- Sample count tracking
- Clear after transmission

### Data Flow

1. **Fetch**: HTML page is fetched and parsed (BeautifulSoup) to extract sensor values from `<tr>` tags with specific IDs (`SID`, `MVAL`, `MUNIT`)
2. **Build**: Plain JSON payload is constructed with sensor data and aligned timestamps
3. **Encrypt**: Payload is encrypted with AES-256 (ECB mode), key derived from SHA256(token_id)
4. **Sign**: RSA signature generated using `{token_id}$*{timestamp}` encrypted with public key
5. **Send**: POST to endpoint with encrypted payload, X-Device-Id header, and signature
6. **Retry**: On failure, payload is queued and retried after next successful send

### Logging Behavior

**Production Mode** (DEV_MODE=false):
- Samples collected every 30 seconds
- Averaged data sent at aligned 15-minute intervals (XX:00, XX:15, XX:30, XX:45)
- ~30 samples averaged per transmission
- Timestamps aligned to 15-min boundaries via [get_aligned_timestamp_ms()](modules/utils.py#L5)
- Flag: "U" (upload)
- Failed sends queued for retry

**Development Mode** (DEV_MODE=true):
- Samples collected every 10 seconds
- Averaged data sent at aligned 1-minute intervals (XX:00, XX:01, XX:02, ...)
- ~6 samples averaged per transmission
- Timestamps aligned to 1-min boundaries
- Flag: "U" (upload)
- Failed sends queued for retry

**Note**: Calibration mode has been removed. Use DEV_MODE in .env for testing with faster intervals.

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
- **Background Retry Thread**: Triggered after successful send ([retry_failed_transmissions()](modules/queue.py#L111))
  - Runs in separate daemon thread to avoid blocking logger thread
  - Processes queue items one by one (FIFO order)
  - **Stops on error**: Exits if any retry gets 4xx/5xx or network error
  - **Removes on 200**: Removes items that get HTTP 200 response (even with wrong data - data errors won't fix themselves)
  - **Auto-exits**: Thread exits when queue is empty
  - Only one retry thread runs at a time (thread-safe with lock)
- Signature regenerated for each retry attempt

### Timestamp Rules

- **Alignment**:
  - Production (DEV_MODE=false): 15-minute boundaries (XX:00, XX:15, XX:30, XX:45)
  - Development (DEV_MODE=true): 1-minute boundaries (XX:00, XX:01, XX:02, ...)
- **Backdate Limit**: Server rejects data older than 7 days
- **Future Dates**: Not allowed
- **Timezone**: All times in IST (Asia/Kolkata)

See [get_aligned_timestamp_ms()](modules/utils.py#L5) for alignment implementation.

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

Use [test_server.py](test_server.py) to verify encryption/decryption and error reporting locally:

### Test Server Features

- **Web UI**: <http://localhost:5000> for configuration
- **Data Endpoint**: <http://localhost:5000/v1.0/industry/data>
- **Error Endpoint**: <http://localhost:5000/ocms/Cpcb/add_cpcberror>
- Simulate HTTP errors (400, 401, 403, 404, 500, 502, 503)
- Simulate ODAMS API errors (all 14 error codes: 10-121)
- Validate credentials from .env
- Decode signature headers
- Console logging with payload decryption

### Testing Steps

1. Run: `python test_server.py` (starts on port 5000)
2. Configure endpoints in .env:

   ```bash
   ENDPOINT=http://localhost:5000/v1.0/industry/data
   ERROR_ENDPOINT_URL=http://localhost:5000/ocms/Cpcb/add_cpcberror
   ```

3. Restart application
4. Use "Test Fetch" and "Test Send" buttons in web UI
5. Check test server console for:
   - Decrypted payloads
   - Error/heartbeat messages
   - Validation results

## Key Implementation Details

- **No File Locking**: Removed - .env is read-only, sensors.json has minimal contention
- **No Config Reloading**: Environment variables loaded once at startup
- **In-Memory Status**: Status tracking doesn't write to disk, improving performance
- **Retry Logic**:
  - **Server errors (5xx)**: 3 attempts with exponential backoff (1s, 2s, 4s), then queued if all fail
  - **Client errors (4xx)**: No retry, immediately queued for later retry
  - **200 OK with wrong response**: No retry, NOT queued (data error)
- **Error Reporting**: Sent once per 15-minute loop, not after every retry attempt
- **Queue Strategy**:
  - 4xx errors → queued (client/request error)
  - 5xx errors → queued after retries fail (server error)
  - 200 with wrong response → NOT queued (data validation error)
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
