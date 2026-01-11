# Test Server Validation Guide

## Overview

The ODAMS test server has been enhanced to **actually validate** payloads for specific error codes instead of just simulating them. This provides more realistic testing of your datalogger's encryption, payload structure, and timestamp alignment.

## Two Types of Errors

### ✅ Actual Validations (Always Active)

These validations happen **automatically** for every request, regardless of the configured test mode:

| Status Code | Validation | Description |
|-------------|------------|-------------|
| **113** | Signature header | Checks if `signature` header is present in request |
| **114** | X-Device-Id header | Checks if `X-Device-Id` header is present in request |
| **115** | Public Key existence | Checks if `PUBLIC_KEY` is configured in .env file |
| **109** | Payload encryption | Actually attempts to decrypt the payload using `TOKEN_ID` from .env |
| **121** | Station/device mapping | Validates payload has proper `stationId` and `deviceId` structure |
| **120** | Multiple stations | Checks if payload contains only one station (multiple not allowed) |
| **119** | Parameter structure | Validates each parameter has: `parameter`, `value`, `unit`, `timestamp`, `flag` |
| **117** | 7-day backdate limit | Checks if timestamp is older than 7 days (IST timezone) |
| **118** | Future timestamp | Checks if timestamp is in the future (IST timezone) |
| **111** | Timestamp alignment | Validates timestamp alignment based on `DEV_MODE`:<br>• DEV_MODE=true: 1-minute boundaries (XX:00, XX:01, XX:02, ...)<br>• DEV_MODE=false: 15-minute boundaries (XX:00, XX:15, XX:30, XX:45) |

**Important:** If any of these validations fail, the test server will immediately return the appropriate error code, even if you have a different error configured in the Web UI.

### ⚠️ Simulated Errors (Configure via Web UI)

These errors are only returned when explicitly configured in the test mode:

| Status Code | Message | When Simulated |
|-------------|---------|----------------|
| **10** | failed | Generic failure - simulated only |
| **102** | Invalid_Station | Station validation - simulated only |
| **110** | Invalid unit | Unit validation - simulated only |
| **112** | No calibration scheduled | Calibration check - simulated only |
| **116** | Device is not registered | Device registration - simulated only |

**Note:** These errors will only be returned if:
1. All actual validations pass (113-121, 109, 111, 117, 118, 119)
2. You have selected "API Error Response" mode in the Web UI
3. You have selected the specific error code in the dropdown

## Testing Workflow

### 1. Run the Test Server

```bash
python test_server.py
```

The server will start on port 5000 and display:
- Current DEV_MODE setting
- Loaded credentials (TOKEN_ID, DEVICE_ID, STATION_ID, PUBLIC_KEY)
- List of actual validations (always active)
- List of simulated errors (configure via Web UI)

### 2. Configure Endpoints in Your Datalogger

Edit your `.env` file:

```bash
ENDPOINT=http://localhost:5000/v1.0/industry/data
ERROR_ENDPOINT_URL=http://localhost:5000/ocms/Cpcb/add_cpcberror
```

Restart your datalogger application.

### 3. Test Actual Validations

These tests happen automatically - just send data and watch the console output:

#### Test Encryption (Status 109)
- **What it tests:** Payload encryption using correct TOKEN_ID
- **How to trigger:** Use wrong TOKEN_ID in test_server.py or datalogger .env
- **Expected result:** Status 109 error with decryption failure message

#### Test Timestamp Alignment (Status 111)
- **What it tests:** Timestamp must align to 1-min (dev) or 15-min (prod) boundaries
- **How to trigger:** Manually modify timestamp in payload to non-aligned value
- **Expected result:** Status 111 error showing timestamp and expected alignment

#### Test 7-Day Backdate (Status 117)
- **What it tests:** Data older than 7 days is rejected
- **How to trigger:** Manually modify timestamp to 8 days ago
- **Expected result:** Status 117 error showing timestamp is too old

#### Test Future Timestamp (Status 118)
- **What it tests:** Future timestamps are rejected
- **How to trigger:** Manually modify timestamp to tomorrow
- **Expected result:** Status 118 error showing future timestamp not allowed

#### Test Missing Headers (Status 113, 114)
- **What it tests:** Required headers must be present
- **How to trigger:** Comment out header setting in datalogger code
- **Expected result:** Status 113 or 114 error

#### Test Parameter Structure (Status 119)
- **What it tests:** Each parameter must have required fields
- **How to trigger:** Modify payload builder to omit a required field
- **Expected result:** Status 119 error showing which field is missing

#### Test Multiple Stations (Status 120)
- **What it tests:** Only one station allowed per payload
- **How to trigger:** Manually create payload with multiple stations in data array
- **Expected result:** Status 120 error listing found stations

#### Test Station/Device Mapping (Status 121)
- **What it tests:** Payload must have proper stationId and deviceId structure
- **How to trigger:** Manually create malformed payload missing these fields
- **Expected result:** Status 121 error showing what's missing

### 4. Test Simulated Errors

After all validations pass, you can test simulated errors:

1. Open Web UI: http://localhost:5000
2. Select "API Error Response" mode
3. Choose an error code (10, 102, 110, 112, 116)
4. Click "Apply Configuration"
5. Send data from datalogger
6. Server will return the selected error (if validations pass)

## Console Output

The test server provides detailed console output showing:

### Validation Failures (Status 109-121)
```
================================================================================
📨 Received Request
================================================================================
Headers:
  X-Device-Id: device_7025
  Signature: bGVuZ3RoOiAxMjggYnl0ZXM=...
  Content-Length: 328

🔓 Decrypting payload...

❌ [ACTUAL VALIDATION] Status 111: Timestamp not aligned to 15-minute boundary: 2026-01-09 14:23:00
  Expected: 15-minute alignment (DEV_MODE=False)
================================================================================
```

### Successful Validation
```
================================================================================
📨 Received Request
================================================================================
Headers:
  X-Device-Id: device_7025
  Signature: bGVuZ3RoOiAxMjggYnl0ZXM=...
  Content-Length: 328

🔓 Decrypting payload...

✅ Decrypted and parsed successfully
📄 Payload:
{
  "data": [
    {
      "stationId": "station_8203",
      "device_data": [
        {
          "deviceId": "device_7025",
          "params": [
            {
              "parameter": "bod",
              "value": "12.5",
              "unit": "mg/L",
              "timestamp": 1736423400000,
              "flag": "U"
            }
          ]
        }
      ]
    }
  ]
}

📅 Timestamp: 1736423400000 (2026-01-09 14:30:00)

✅ All validations passed!

✅ Credentials validated successfully

✅ Returning success response
================================================================================
```

## DEV_MODE Impact

The test server reads `DEV_MODE` from .env file and adjusts timestamp alignment validation:

- **DEV_MODE=true**: Expects 1-minute alignment (XX:00, XX:01, XX:02, ...)
- **DEV_MODE=false**: Expects 15-minute alignment (XX:00, XX:15, XX:30, XX:45)

**Important:** Make sure the test server's .env has the same `DEV_MODE` setting as your datalogger.

## Web UI Features

The Web UI at http://localhost:5000 shows:

1. **Server Configuration**
   - Response mode selector (Success / HTTP Error / API Error)
   - HTTP status code selector (400, 401, 403, 404, 500, 502, 503)
   - API error code selector (10, 102, 109-121)
   - Credential validation toggle
   - Signature decoding toggle

2. **Loaded Credentials**
   - Shows credentials loaded from .env file
   - Helps verify test server is using correct config

3. **Error Codes Reference**
   - Complete table of all ODAMS error codes
   - Color-coded by type (✓ Validation / ⚠ Simulation)
   - Descriptions of what each code validates

4. **How Validation Works**
   - Detailed explanation of actual validations
   - List of simulated errors
   - Current DEV_MODE setting

## Testing Best Practices

### 1. Start with Success Mode
- Set test server to "Success Response" mode
- Verify all validations pass
- Check console output for payload structure

### 2. Test Each Validation
- Test one validation at a time
- Verify error is returned as expected
- Check console output for detailed error message

### 3. Test Simulated Errors
- After validations pass, test simulated errors
- Verify datalogger handles different error codes correctly
- Check queue behavior for different status codes

### 4. Test Queue Retry Logic
- Use simulated Status 10 to test queuing behavior
- Verify failed transmissions are queued
- Verify retry logic works after successful send

### 5. Test Error Reporting
- Monitor error endpoint for heartbeat and error messages
- Verify error context includes proper device/station info

## Troubleshooting

### Status 109 (Decryption Failed)
- **Cause:** TOKEN_ID mismatch between datalogger and test server
- **Fix:** Ensure both .env files have same TOKEN_ID (base64 encoded)

### Status 111 (Timestamp Alignment)
- **Cause:** Timestamp not aligned to expected boundaries
- **Fix:** Check DEV_MODE setting matches between datalogger and test server

### Status 113/114 (Missing Headers)
- **Cause:** Headers not being sent correctly
- **Fix:** Check network.py send_to_server() function includes headers

### Status 115 (Public Key Missing)
- **Cause:** PUBLIC_KEY not configured in test server .env
- **Fix:** Copy PUBLIC_KEY from datalogger .env to test server .env

### Status 117 (Too Old)
- **Cause:** Timestamp is older than 7 days
- **Fix:** Check system clock is correct (IST timezone)

### Status 118 (Future Timestamp)
- **Cause:** Timestamp is in the future
- **Fix:** Check system clock is correct (IST timezone)

### Status 119 (Invalid Parameter)
- **Cause:** Parameter missing required fields
- **Fix:** Check payload.py builds all required fields: parameter, value, unit, timestamp, flag

### Status 120 (Multiple Stations)
- **Cause:** Payload has multiple stations
- **Fix:** Check payload builder only includes one station

### Status 121 (Missing Mapping)
- **Cause:** stationId or deviceId missing from payload structure
- **Fix:** Check payload.py includes proper structure

## Summary

The improved test server provides **realistic validation** of your datalogger's:
- Encryption implementation (Status 109)
- Timestamp alignment logic (Status 111)
- Payload structure (Status 119, 120, 121)
- Header implementation (Status 113, 114)
- Timestamp validation (Status 117, 118)

Combined with **simulated errors** (Status 10, 102, 110, 112, 116), you can thoroughly test all aspects of your datalogger's error handling and retry logic before deploying to production.

**Use this test server during development to catch issues early!**
