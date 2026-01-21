# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Flask-based sensor datalogger application that:

- Fetches sensor data from multiple sources:
  - **IQ Web Connect**: HTML pages (via HTTP or local file://)
  - **Modbus TCP**: Direct TCP/IP connection to Modbus devices
  - **Modbus RTU**: RS485 serial connection to Modbus devices
  - **Analog (4-20mA)**: Waveshare analog acquisition module via REST API
- Encrypts payloads using AES-256 and signs with RSA
- Transmits to ODAMS/CPCB servers with retry logic
- Runs 24/7 on Raspberry Pi with systemd integration
- Provides a web admin interface for configuration and monitoring
- Includes test server with actual payload validation

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

# Run test server for local testing (with actual validations)
python test_server.py
# Configure endpoint in .env to: http://localhost:5000/v1.0/industry/data

# Run analog acquisition server (separate device or localhost)
python analogserver.py
# Access web UI at http://localhost:8000
```

### Production (Raspberry Pi)
```bash
# Install sudoers configuration (for auto-restart on internet timeout)
sudo cp sudoers-datalogger /etc/sudoers.d/datalogger
sudo chmod 440 /etc/sudoers.d/datalogger
sudo visudo -c -f /etc/sudoers.d/datalogger  # Verify syntax

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
5. **Diagnostic Monitor Thread** ([modules/diagnostics.py](modules/diagnostics.py)): Continuous internet connectivity monitoring
   - Checks internet every 5 minutes (configurable)
   - Tracks time since last successful connection
   - Auto-restarts system after 30+ minutes without internet (configurable)
   - Restart cooldown prevents boot loops
   - Sends error notification before restart
6. **Retry Queue Thread** ([modules/queue.py:40](modules/queue.py#L40)): Dynamic background worker (spawned as needed)
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
├── diagnostics.py       # Pre-startup diagnostics and continuous internet monitoring
├── network.py           # Data fetching, server transmission, error reporting
├── crypto.py            # AES encryption + RSA signature generation
├── payload.py           # JSON payload construction
├── queue.py             # Failed transmission queue with retry logic
├── utils.py             # Timestamp alignment utilities
├── routes.py            # Flask web routes (/health, /test_fetch, /test_send, /diagnostics)
├── modbus_fetcher.py    # Modbus TCP sensor data fetching
├── modbus_rtu_fetcher.py # Modbus RTU (RS485) sensor data fetching
└── constants.py         # Shared constants, logging setup

analogserver.py          # Standalone analog acquisition server (Waveshare 4-20mA module)
test_server.py           # ODAMS test server with actual payload validation
datalogger-wrapper.sh    # Simplified systemd wrapper (activates venv, starts app)
sudoers-datalogger       # Sudoers config template for passwordless reboot
```

### Supported Sensor Types

The datalogger supports four sensor types, all configurable via web UI:

#### 1. IQ Web Connect (HTML Parsing)

Fetches sensor data from HTML pages (HTTP or file://).

**Configuration:**

- `sensor_id`: Sensor ID from HTML (matches SID* tags)
- `param_name`: CPCB parameter name
- `unit`: Optional (fetched from HTML if not specified)

**Data Source:** Configured via `DATAPAGE_URL` in .env

**Implementation:** [modules/network.py](modules/network.py) - `fetch_sensor_data()`

**HTML Structure Required:**

```html
<tr class="EvenRow">
  <td id="SID1">S01</td>          <!-- sensor_id -->
  <td id="MVAL1">12.5</td>        <!-- value -->
  <td id="MUNIT1">mg/L</td>       <!-- unit -->
</tr>
```

#### 2. Modbus TCP

Direct TCP/IP connection to Modbus devices.

**Configuration:**

- `ip`: Device IP address (e.g., 192.168.1.100)
- `port`: Modbus port (default: 502)
- `slave_id`: Modbus slave ID (1-247)
- `register_type`: holding, input, coil, discrete
- `register_address`: Register address (0-65535)
- `data_type`: uint16, int16, uint32, int32, float32, uint8_high/low, int8_high/low
- `byte_order`: big, little (for multi-byte values)
- `word_order`: big, little (for 32-bit values)
- `param_name`: CPCB parameter name
- `unit`: Unit for this parameter (required)

**Implementation:** [modules/modbus_fetcher.py](modules/modbus_fetcher.py) - `fetch_modbus_tcp_sensors()`

**Features:**

- Support for all standard Modbus data types
- Configurable byte/word ordering for compatibility
- Efficient batching (one connection per device)

#### 3. Modbus RTU (RS485)

Serial/RS485 connection to Modbus RTU devices.

**Device Configuration (shared across all RTU sensors):**

- `port`: Serial port (COM7, /dev/ttyUSB0)
- `baudrate`: 9600, 19200, 38400, 57600, 115200
- `parity`: N (None), E (Even), O (Odd)
- `bytesize`: 7 or 8
- `stopbits`: 1 or 2
- `timeout`: Communication timeout (seconds)

**Per-Sensor Configuration:**

- `slave_id`: Modbus slave ID (1-247)
- `register_type`, `register_address`, `data_type`: Same as Modbus TCP
- `byte_order`, `word_order`: Same as Modbus TCP
- `param_name`: CPCB parameter name
- `unit`: Unit for this parameter (required)

**Implementation:** [modules/modbus_rtu_fetcher.py](modules/modbus_rtu_fetcher.py) - `fetch_modbus_rtu_sensors()`

**Notes:**

- Only one RTU device (serial port) supported
- Multiple sensors can share the same bus with different slave IDs
- Serial port configuration shared across all RTU sensors

#### 4. Analog (4-20mA via Waveshare Module)

Fetches data from Waveshare Modbus RTU Analog Input 8CH module via REST API.

**Architecture:**

- Analog server runs on separate device (or localhost for testing)
- Reads 4-20mA signals from Waveshare module
- Provides REST API for datalogger to fetch data
- Web UI for scaling configuration (4-20mA to engineering units)

**Configuration:**

- `server_url`: URL of analog acquisition server (e.g., http://192.168.1.100:8000)
- `channel_id`: Waveshare channel number (1-8)
- `param_name`: CPCB parameter name
- `unit`: Unit for this parameter (required, should match analog server)

**Implementation:** [modules/network.py](modules/network.py) - `fetch_analog_sensors()`

**Setup:**

1. Run `analogserver.py` on device connected to Waveshare module
2. Configure channels with scaling in analog server web UI (port 8000)
3. Configure analog sensors in datalogger web UI with server URL

**Documentation:**

- [ANALOG_SERVER_GUIDE.md](ANALOG_SERVER_GUIDE.md) - Standalone analog server setup
- [ANALOG_INTEGRATION_GUIDE.md](ANALOG_INTEGRATION_GUIDE.md) - Integration with datalogger

**Features:**

- Linear scaling from 4-20mA to engineering units
- Web UI for easy configuration
- Network-based architecture (flexible deployment)
- Multiple dataloggers can read from one analog server
- Efficient fetching (one API call per server for all channels)

### Mixing Sensor Types

All sensor types can be used simultaneously. The datalogger fetches data from all configured sensors, averages them, and sends to CPCB/ODAMS together.

**Example Configuration:**

```json
{
  "sensors": [
    {
      "type": "iq_web_connect",
      "sensor_id": "S01",
      "param_name": "ph",
      "unit": "pH"
    },
    {
      "type": "modbus_tcp",
      "ip": "192.168.1.50",
      "slave_id": 1,
      "register_type": "holding",
      "register_address": 100,
      "data_type": "float32",
      "param_name": "temperature",
      "unit": "°C"
    },
    {
      "type": "modbus_rtu",
      "slave_id": 2,
      "register_type": "input",
      "register_address": 0,
      "data_type": "uint16",
      "param_name": "pressure",
      "unit": "bar"
    },
    {
      "type": "analog",
      "server_url": "http://192.168.1.100:8000",
      "channel_id": 1,
      "param_name": "flow",
      "unit": "m³/hr"
    }
  ]
}
```

### Diagnostic System

The datalogger includes a comprehensive diagnostic system that handles pre-startup checks and continuous monitoring to ensure reliable 24/7 operation on Raspberry Pi.

#### Pre-Startup Diagnostics (Blocking Phase)

Runs once at application startup before any other components initialize:

1. **Modem Detection & Configuration** ([modules/diagnostics.py](modules/diagnostics.py) - `find_quectel_modem()`, `configure_quectel_modem()`)
   - Scans USB serial ports for Quectel EC200U/G modem
   - Excludes RS485 converters (CH340, FT232, CP210)
   - Sends AT commands to enable network mode
   - Retries up to 3 times with 2-second delays
   - Continues startup even if modem not found (ethernet may work)

2. **Network Interface Check** ([modules/diagnostics.py](modules/diagnostics.py) - `check_network_interface()`)
   - Waits for eth0 to get IP address (max 120 seconds)
   - Uses `ip addr show` command to check interface
   - Logs IP address when assigned
   - Continues startup even if timeout (application has retry logic)

3. **Internet Connectivity Check** ([modules/diagnostics.py](modules/diagnostics.py) - `check_internet_connectivity()`)
   - Tests connectivity via HTTP requests to multiple endpoints:
     - Google (https://www.google.com)
     - Cloudflare DNS (https://1.1.1.1)
     - CPCB Portal (http://portal.cpcbocems.com)
   - Accepts various HTTP success codes (200, 301, 302, 303, 307, 308)
   - Continues startup even if fails (monitoring will track)

4. **Network Stability Wait**
   - Waits 30 seconds for network to stabilize after IP assignment
   - Ensures modem/network is fully ready before starting data operations

**Total Startup Time:** 40-160 seconds depending on network availability

**Implementation:** All pre-startup diagnostics run in `run_pre_startup_diagnostics()` called from [datalogger_app.py](datalogger_app.py) before initializing other threads.

#### Continuous Monitoring (Non-Blocking Phase)

Background thread that monitors system health and triggers recovery actions:

**Internet Connectivity Monitoring** ([modules/diagnostics.py](modules/diagnostics.py) - `DiagnosticMonitor` class)

- Checks internet connectivity at regular intervals (default: 5 minutes)
- Tracks time since last successful connection
- Auto-restarts system if internet unavailable for extended period (default: 30 minutes)
- Prevents boot loops with restart cooldown (default: 30 minutes)
- Sends error notification before restarting

**Safety Features:**
- Enable/disable flag to prevent unwanted restarts during testing
- Restart cooldown prevents rapid restart loops
- Graceful shutdown with error notification
- Thread-safe status tracking

**Web Interface:** Status visible at `/diagnostics` page showing:
- Last check time
- Last successful internet connection
- Time without internet
- Consecutive failures count
- Restart count and last restart time
- Current configuration

#### Configuration (via .env)

```bash
# How often to check internet connectivity (in minutes)
DIAGNOSTIC_CHECK_INTERVAL_MINUTES=5

# Auto-restart system after this many minutes without internet
DIAGNOSTIC_INTERNET_TIMEOUT_MINUTES=30

# Enable/disable automatic system restart on internet timeout
DIAGNOSTIC_AUTO_RESTART_ENABLED=true

# Minimum time between system restarts (prevents boot loops)
DIAGNOSTIC_RESTART_COOLDOWN_MINUTES=30
```

**Default values:** If not specified, defaults are: 5min check interval, 30min timeout, auto-restart enabled, 30min cooldown.

#### Passwordless Reboot Setup

For auto-restart to work, the application user needs sudo permission for reboot command:

```bash
# Install sudoers configuration
sudo cp sudoers-datalogger /etc/sudoers.d/datalogger
sudo chmod 440 /etc/sudoers.d/datalogger
sudo visudo -c -f /etc/sudoers.d/datalogger  # Verify syntax
```

The sudoers file grants ONLY reboot permission (no shell access):
```
logger ALL=(ALL) NOPASSWD: /sbin/reboot
```

#### Adding Custom Diagnostics

The diagnostic module is designed for easy extension. To add custom checks:

**Example: Disk Space Monitoring**

```python
# In modules/diagnostics.py

def check_disk_space() -> DiagnosticResult:
    """Check available disk space."""
    import shutil
    stat = shutil.disk_usage('/')
    percent_free = (stat.free / stat.total) * 100

    if percent_free > 10:
        return DiagnosticResult("Disk Space", True, f"{percent_free:.1f}% free")
    else:
        return DiagnosticResult("Disk Space", False, f"Only {percent_free:.1f}% free")

# Add to pre-startup diagnostics
def run_pre_startup_diagnostics():
    # ... existing checks ...
    results.append(check_disk_space())
    # ...
```

**Example: CPU Temperature Monitoring**

```python
# Add to DiagnosticMonitor._perform_check() for continuous monitoring

def _perform_check(self):
    # ... existing internet check ...

    # Check CPU temperature
    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
        temp = int(f.read().strip()) / 1000

    if temp > 80:
        logger.warning(f"High CPU temperature: {temp}°C")
        from modules.network import send_error_to_endpoint
        send_error_to_endpoint("HIGH_TEMPERATURE", f"CPU: {temp}°C")
```

#### Troubleshooting

**Modem not detected:**
- Check USB connection
- Verify modem is Quectel EC200U/G
- Check if being detected as RS485 converter (exclude list)
- Application continues without modem (ethernet may work)

**Network interface timeout:**
- Check ethernet cable connection
- Verify network switch/router is working
- Check if DHCP server is available
- Application continues (retry logic handles network issues)

**Auto-restart not working:**
- Verify sudoers file is installed correctly
- Check user has permission: `sudo -l` should show `/sbin/reboot`
- Check if `DIAGNOSTIC_AUTO_RESTART_ENABLED=true` in .env
- Check logs for error messages

**Restart loop:**
- Restart cooldown should prevent this (default 30 minutes)
- If loop occurs, increase `DIAGNOSTIC_RESTART_COOLDOWN_MINUTES`
- Disable auto-restart: `DIAGNOSTIC_AUTO_RESTART_ENABLED=false`
- Fix underlying network issue

**View diagnostic status:**
- Web UI: http://localhost:9999/diagnostics
- Logs: `tail -f datalogger.log | grep -i diagnostic`

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

### Data Fetching Flow

The datalogger uses [modules/network.py](modules/network.py) - `fetch_all_sensors()` to collect data from all configured sensor types:

1. **Group sensors by type** (IQ Web Connect, Modbus TCP, Modbus RTU, Analog)
2. **Fetch from each type in parallel** (when possible)
3. **Return unified dictionary** mapping param_name to {value, unit}
4. **Store in data collector** for averaging

**Efficiency optimizations:**

- IQ Web Connect: One HTML fetch for all sensors on same page
- Modbus TCP: One connection per device IP
- Modbus RTU: One serial connection for all sensors
- Analog: One API call per server URL (fetches all channels)

## Testing

Use [test_server.py](test_server.py) to verify encryption/decryption and error reporting locally.

### Test Server Features

The test server provides realistic testing with **actual payload validation** instead of just simulating errors.

**Endpoints:**

- **Web UI**: <http://localhost:5000> for configuration
- **Data Endpoint**: <http://localhost:5000/v1.0/industry/data>
- **Error Endpoint**: <http://localhost:5000/ocms/Cpcb/add_cpcberror>

**Validation Types:**

1. **Actual Validations** (always active, regardless of test mode):
   - **Status 109**: Payload encryption - actually decrypts using TOKEN_ID
   - **Status 111**: Timestamp alignment - validates 1-min (dev) or 15-min (prod) boundaries
   - **Status 113**: Signature header presence check
   - **Status 114**: X-Device-Id header presence check
   - **Status 115**: Public key existence check
   - **Status 117**: 7-day backdate limit validation
   - **Status 118**: Future timestamp validation
   - **Status 119**: Parameter structure validation (all required fields)
   - **Status 120**: Multiple stations check (only one allowed)
   - **Status 121**: Station/device mapping validation

2. **Simulated Errors** (configured via web UI):
   - Status 10, 102, 110, 112, 116
   - Only returned if all actual validations pass

**Features:**

- Reads DEV_MODE from .env for correct timestamp alignment validation
- Decrypts and displays payloads in console
- Validates credentials from .env
- Decodes signature headers
- Detailed console logging with validation results
- Color-coded error types in web UI (✓ Validation / ⚠ Simulation)

**Documentation:** See [TEST_SERVER_VALIDATION.md](TEST_SERVER_VALIDATION.md) for complete guide.

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
   - Decrypted payloads with full structure
   - Actual validation results (encryption, timestamps, structure)
   - Error/heartbeat messages
   - Pass/fail status for each validation

### Testing Best Practices

1. **Start with Success Mode**: Verify all validations pass before testing errors
2. **Test Each Validation**: Intentionally break one validation at a time to verify detection
3. **Test Simulated Errors**: After validations pass, test datalogger's error handling
4. **Match DEV_MODE**: Ensure test server and datalogger have same DEV_MODE setting
5. **Check Payload Structure**: Verify decrypted payload matches expected format

### Analog Server Testing

For analog sensor integration:

1. Run `python analogserver.py` (starts on port 8000)
2. Access web UI at <http://localhost:8000>
3. Configure channels with scaling (4-20mA to engineering units)
4. Monitor real-time readings in "Monitor" tab
5. Test API endpoints: `curl http://localhost:8000/api/channels`
6. Configure datalogger to fetch from `http://localhost:8000`

**Documentation:** See [ANALOG_SERVER_GUIDE.md](ANALOG_SERVER_GUIDE.md) and [ANALOG_INTEGRATION_GUIDE.md](ANALOG_INTEGRATION_GUIDE.md).

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

The web interface ([modules/routes.py](modules/routes.py)) provides:

### Pages

1. **Dashboard** (`/`) - Real-time sensor monitoring
   - Current sensor values with last update time
   - System status (server running, last fetch/send times)
   - Queue status
   - Sensor type badges (IQ Web Connect, Modbus TCP, Modbus RTU, Analog)

2. **Configuration** (`/config`) - Environment variables (read-only)
   - Displays .env values (TOKEN_ID, DEVICE_ID, STATION_ID, etc.)
   - Cannot be edited (must edit .env file and restart)

3. **Sensors** (`/sensors`) - Sensor configuration
   - **Four tabs**: IQ Web Connect, Modbus TCP, Modbus RTU (RS485), Analog
   - Add/remove sensors of each type
   - Configure sensor-specific parameters
   - RTU device configuration (serial port settings)
   - Save configuration to sensors.json

4. **Queue** (`/queue`) - Failed transmissions queue
   - View queued payloads
   - Clear queue manually
   - Queue statistics

5. **Diagnostics** (`/diagnostics`) - System diagnostic monitoring
   - Monitor status (running/stopped)
   - Internet connectivity status
   - Time without internet
   - Consecutive failures count
   - Restart count and last restart time
   - Configuration settings (check interval, timeout, auto-restart)
   - Real-time diagnostic status updates

6. **Logs** (`/logs`) - Application logs viewer
   - View recent log entries
   - Filter by level
   - Download logs

### Features

- **HTTP Basic Auth**: Username: admin, Password: admin123
- **Test Buttons**: Test Fetch and Test Send for quick verification
- **Real-time Updates**: Dashboard refreshes automatically
- **Responsive Design**: Works on mobile and desktop

**Note**: Changes to .env require application restart. Sensor configuration changes take effect on next logger cycle.

## Recent Changes & Features

### Diagnostic System Implementation (Latest)

Comprehensive diagnostic module for reliable 24/7 operation:

- **New Files**:
  - `modules/diagnostics.py` - Pre-startup diagnostics and continuous monitoring
  - `templates/diagnostics.html` - Web UI for diagnostic status
  - `sudoers-datalogger` - Sudoers config template for passwordless reboot

- **Modified Files**:
  - `datalogger_app.py` - Added pre-startup diagnostics and monitoring thread
  - `datalogger-wrapper.sh` - Simplified (removed shell-based checks, moved to Python)
  - `modules/routes.py` - Added `/diagnostics` endpoint
  - `.env` - Added diagnostic configuration variables

- **Features**:
  - **Pre-Startup Diagnostics**: Modem detection/configuration, network interface check, internet connectivity check
  - **Continuous Monitoring**: Internet connectivity checks every 5 minutes
  - **Auto-Recovery**: System restart after 30+ minutes without internet
  - **Safety Features**: Restart cooldown, enable/disable flag, error notifications
  - **Web Interface**: Real-time diagnostic status at `/diagnostics` page
  - **Extensible**: Easy to add custom diagnostic checks
  - **All-Python**: Better error handling, logging integration, no shell scripts

- **Replaced**:
  - `findcdcport.py` - Functionality integrated into diagnostics module
  - Shell-based network checks in wrapper script - Now handled in Python

### Analog Sensor Integration

Added support for 4-20mA analog sensors via Waveshare Modbus RTU Analog Input 8CH module:

- **New Files**:
  - `analogserver.py` - Standalone analog acquisition server with REST API
  - `ANALOG_SERVER_GUIDE.md` - Server setup and configuration guide
  - `ANALOG_INTEGRATION_GUIDE.md` - Integration with datalogger guide

- **Modified Files**:
  - `modules/network.py` - Added `fetch_analog_sensors()` function
  - `modules/config.py` - Added validation for analog sensor type
  - `templates/sensors.html` - Added Analog tab with UI for configuration
  - `templates/dashboard.html` - Added analog sensor display

- **Features**:
  - Network-based architecture (analog server can run on separate device)
  - Web UI for scaling configuration (4-20mA to engineering units)
  - REST API for fetching channel data
  - Efficient fetching (one API call per server for all 8 channels)
  - Configurable units in datalogger (consistent with other sensor types)

### Test Server Validation Improvements

Enhanced test server with actual payload validation:

- **Actual Validations** (Status 109, 111, 113-121):
  - Actually decrypts payloads using TOKEN_ID
  - Validates timestamp alignment based on DEV_MODE
  - Checks payload structure (stationId, deviceId, parameters)
  - Validates backdate/future timestamp limits
  - These run automatically, not just simulated

- **Documentation**:
  - `TEST_SERVER_VALIDATION.md` - Complete testing guide with validation details

- **Console Output**: Detailed logging showing:
  - Decrypted payload structure
  - Validation pass/fail for each check
  - Expected vs actual values for failed validations

### Modbus RTU Support

Added serial/RS485 Modbus support:

- **New File**: `modules/modbus_rtu_fetcher.py`
- Shared serial port configuration across all RTU sensors
- Multiple slaves supported on same RS485 bus
- All Modbus data types supported (same as Modbus TCP)

### Data Averaging Implementation

Continuous sampling with averaging:

- **New File**: `modules/data_collector.py`
- Separate threads for data collection vs transmission
- Production: 30-second sampling, 15-minute averaging
- Development: 10-second sampling, 1-minute averaging
- Reduces noise and provides more representative readings

## Project History

- **Initial Release**: IQ Web Connect HTML parsing, basic encryption
- **Modbus TCP**: Added direct Modbus TCP/IP support
- **Modbus RTU**: Added RS485/serial Modbus support
- **Data Averaging**: Continuous sampling with averaging system
- **Test Server Validation**: Enhanced test server with actual validations
- **Analog Integration**: Added 4-20mA analog sensor support via Waveshare module
- **Diagnostic System**: Pre-startup diagnostics and continuous internet monitoring with auto-recovery

## Related Documentation

- [README.md](README.md) - Project overview and setup
- [CLAUDE.md](CLAUDE.md) - This file (development guide)
- [ANALOG_SERVER_GUIDE.md](ANALOG_SERVER_GUIDE.md) - Analog server setup
- [ANALOG_INTEGRATION_GUIDE.md](ANALOG_INTEGRATION_GUIDE.md) - Analog integration guide
- [TEST_SERVER_VALIDATION.md](TEST_SERVER_VALIDATION.md) - Test server validation guide
