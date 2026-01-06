import time
import math
from datetime import datetime

from .constants import IST, logger
from .config import load_sensors_config, get_env
from .status import status
from .crypto import encrypt_payload
from .payload import build_plain_payload
from .network import (
    send_to_server,
    fetch_sensor_data,
    fetch_all_sensors,
    send_error_to_endpoint
)
from .queue import load_queue, save_queue, retry_failed_transmissions
from .utils import get_aligned_timestamp_ms


def heartbeat_thread():
    """Send IP heartbeat every 30 minutes"""

    while True:
        try:
            sensors_config = load_sensors_config()

            # Only send heartbeat if server is running
            if sensors_config.get('server_running', False):
                heartbeat_msg = f"System Running"

                logger.debug(f"Sending heartbeat: {heartbeat_msg}")
                send_error_to_endpoint("HEARTBEAT", heartbeat_msg)

            # Wait 30 minutes before next heartbeat
            time.sleep(30 * 60)

        except Exception as e:
            logger.error(f"Error in heartbeat thread: {e}")
            time.sleep(30 * 60)


def logger_thread():
    """Background thread for data logging - uses 15-minute intervals (1-minute in DEV_MODE)"""
    last_send = 0

    # Check if DEV_MODE is enabled
    dev_mode = get_env('dev_mode', False)
    alignment_minutes = 1 if dev_mode else 15
    interval_seconds = alignment_minutes * 60

    if dev_mode:
        logger.info("DEV_MODE enabled - using 1-minute intervals")
    else:
        logger.info("Production mode - using 15-minute intervals")

    now = datetime.now(IST)

    # Calculate next aligned time
    current_ts = now.timestamp()
    aligned_ts = math.ceil(current_ts / interval_seconds) * interval_seconds
    next_send_time = aligned_ts

    while True:
        try:
            sensors_config = load_sensors_config()

            if not sensors_config.get('server_running', False):
                time.sleep(5)
                continue

            current = time.time()

            should_send = False
            if last_send == 0:
                # First send: wait for next aligned time
                if current >= next_send_time:
                    should_send = True
                    last_send = next_send_time
                else:
                    sleep_time = min(5, next_send_time - current)
                    time.sleep(sleep_time)
                    continue
            else:
                # Subsequent sends: check interval
                if current - last_send >= interval_seconds:
                    should_send = True
                    last_send += interval_seconds
                else:
                    time.sleep(5)
                    continue

            if should_send:
                # Fetch new data from all sensor types
                sensors = fetch_all_sensors(sensors_config)

                if sensors:
                    # Update fetch success
                    expected_count = len(sensors_config.get('sensors', []))
                    if len(sensors) == expected_count:
                        status.update_fetch_success()

                    logger.debug(f"Fetched sensors: {sensors}")

                    # Send data (always with aligned timestamps and 'U' flag)
                    success, status_code, text, should_queue = send_to_server(sensors)

                    status.increment_sends()

                    if success:
                        status.update_send_success()
                        status.clear_error()
                        logger.info("Data sent successfully")

                        # Retry queued data after successful send
                        retry_failed_transmissions()
                    else:
                        status.increment_failed()
                        status.set_error(f"Status {status_code}: {text}")

                        # Send error to endpoint once per loop (15 minutes)
                        send_error_to_endpoint("SEND_FAILED", status.last_error)

                        # Queue encrypted payload for retry only if should_queue is True
                        if should_queue:
                            device_id = get_env('device_id', '')
                            station_id = get_env('station_id', '')
                            token_id = get_env('token_id', '')

                            plain_json = build_plain_payload(sensors, device_id, station_id)
                            encrypted_payload = encrypt_payload(plain_json, token_id)
                            # Use same alignment as build_plain_payload
                            aligned_ts = get_aligned_timestamp_ms(alignment_minutes)
                            queue = load_queue()
                            queue.append({
                                'encrypted_payload': encrypted_payload,
                                'timestamp': datetime.now(IST).isoformat(),
                                'aligned_ts': aligned_ts
                            })
                            save_queue(queue[-100:])  # Keep last 100
                            logger.info(f"Queued failed transmission for retry")
                        else:
                            logger.error(f"Data error - not queuing: {text}")

            time.sleep(5)

        except Exception as e:
            logger.error(f"Error in logger thread: {e}")
            time.sleep(10)
