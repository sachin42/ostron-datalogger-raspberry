import time
import math
from datetime import datetime

from .constants import IST, logger
from .config import load_config, save_config
from .crypto import encrypt_payload
from .payload import build_plain_payload
from .network import (
    send_to_server,
    fetch_sensor_data,
    send_error_to_endpoint,
    get_public_ip
)
from .queue import load_queue, save_queue, retry_failed_transmissions
from .utils import get_aligned_timestamp_ms


def heartbeat_thread():
    """Send IP heartbeat every 30 minutes"""
    # Wait 30 minutes before first heartbeat
    time.sleep(30 * 60)

    while True:
        try:
            config = load_config()

            # Only send heartbeat if server is running
            if config.get('server_running', False):
                public_ip = get_public_ip()
                heartbeat_msg = f"Heartbeat - System Running - IP: {public_ip}"

                logger.info(f"Sending heartbeat: {heartbeat_msg}")
                send_error_to_endpoint("HEARTBEAT", heartbeat_msg, config)

            # Wait 30 minutes before next heartbeat
            time.sleep(30 * 60)

        except Exception as e:
            logger.error(f"Error in heartbeat thread: {e}")
            time.sleep(30 * 60)


def logger_thread():
    """Background thread for data logging"""
    last_send = 0
    config = load_config()  # Load once for alignment calc
    alignment_minutes = 1 if config.get('calibration_mode', False) else 15
    interval_seconds = alignment_minutes * 60
    now = datetime.now(IST)
    # Calculate next aligned time
    current_ts = now.timestamp()
    aligned_ts = math.ceil(current_ts / interval_seconds) * interval_seconds
    next_send_time = aligned_ts

    while True:
        try:
            config = load_config()

            if not config.get('server_running', False):
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
                # Fetch new data
                config_sensors = {s['sensor_id']: s for s in config.get('sensors', [])}
                sensors = fetch_sensor_data(config.get('datapage_url', ''), config_sensors, config)

                if sensors:
                    # Update fetch success if we got all sensors
                    if len(sensors) == len(config_sensors):
                        config['last_fetch_success'] = datetime.now(IST).isoformat()

                    logger.info(f"Fetched sensors: {sensors}")

                    # Send data
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

                    config['total_sends'] = config.get('total_sends', 0) + 1

                    if success:
                        config['last_send_success'] = datetime.now(IST).isoformat()
                        config['last_error'] = ""
                        logger.info("Data sent successfully")
                        # Retry queued data after successful send
                        retry_failed_transmissions(config)
                    else:
                        config['failed_sends'] = config.get('failed_sends', 0) + 1
                        config['last_error'] = f"Status {status}: {text}"

                        # Send error after 3 failed attempts
                        send_error_to_endpoint("SEND_FAILED", config['last_error'], config)

                        # Queue encrypted payload for retry (not in calibration mode)
                        if not config.get('calibration_mode', False):
                            flag = "C" if config.get('calibration_mode', False) else "U"
                            plain_json = build_plain_payload(sensors, config.get('device_id', ''),
                                                             config.get('station_id', ''), flag=flag)
                            encrypted_payload = encrypt_payload(plain_json, config.get('token_id', ''))
                            aligned_ts = get_aligned_timestamp_ms()
                            queue = load_queue()
                            queue.append({
                                'encrypted_payload': encrypted_payload,
                                'timestamp': datetime.now(IST).isoformat(),
                                'aligned_ts': aligned_ts
                            })
                            save_queue(queue[-100:])  # Keep last 100
                        logger.error(f"Failed to send data: {text}")

                save_config(config)

            time.sleep(5)

        except Exception as e:
            logger.error(f"Error in logger thread: {e}")
            time.sleep(10)
