import json
import os
import time
import threading
import requests
from typing import List

from .constants import QUEUE_FILE, logger
from .config import get_env
from .crypto import generate_signature

# Global flag to track if retry thread is running
_retry_thread_running = False
_retry_thread_lock = threading.Lock()


def load_queue() -> List[dict]:
    """Load failed transmission queue"""
    if not os.path.exists(QUEUE_FILE):
        return []

    try:
        with open(QUEUE_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading queue: {e}")
        return []


def save_queue(queue: List[dict]):
    """Save failed transmission queue"""
    try:
        with open(QUEUE_FILE, 'w') as f:
            logger.debug(f"Saving queue with {len(queue)} items")
            json.dump(queue, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving queue: {e}")


def _retry_queue_worker():
    """Background worker thread to retry queued transmissions"""
    global _retry_thread_running

    try:
        endpoint = get_env('endpoint', "https://cems.cpcb.gov.in/v1.0/industry/data")
        token_id = get_env('token_id', '')
        public_key_pem = get_env('public_key', '')
        device_id = get_env('device_id', '')

        while True:
            queue = load_queue()
            if not queue:
                logger.debug("Queue empty, retry thread exiting")
                break

            item = queue[0]  # Process first item
            current_ts = int(time.time() * 1000)

            # Check if data is too old (backdate limit 7 days)
            if 'aligned_ts' in item and (current_ts - item['aligned_ts']) > 7 * 24 * 60 * 60 * 1000:
                logger.warning(f"Removing old queued data from {item['timestamp']}")
                queue.pop(0)
                save_queue(queue[-100:])
                continue

            try:
                # Regenerate signature with current time
                signature = generate_signature(token_id, public_key_pem)

                headers = {
                    "Content-Type": "text/plain",
                    "X-Device-Id": device_id,
                    "signature": signature
                }

                response = requests.post(endpoint, data=item['encrypted_payload'], headers=headers, timeout=90)
                logger.debug(f"Retry send status: {response.status_code} - {response.text}")

                if response.status_code == 200:
                    remove_from_queue = False
                    try:
                        data = json.loads(response.text.strip())
                        if data.get('msg') == 'success' and data.get('status') == 1:
                            # Success - remove from queue
                            logger.info(f"Successfully sent queued data from {item['timestamp']}")
                            remove_from_queue = True
                        else:
                            # Check if it's ODAMS status 10 (server error, should keep in queue)
                            status_code = data.get('status')
                            if status_code == 10:
                                # ODAMS status 10 - server error, keep in queue, stop retry (will retry later)
                                logger.error(f"ODAMS status 10 (failed) for queued data - keeping in queue: {data.get('msg', 'Unknown error')}")
                                break  # Stop retry thread, keep item in queue
                            else:
                                # Other error status - data error, remove from queue
                                logger.warning(f"Data error for queued data (status {status_code}) - removing from queue: {response.text}")
                                remove_from_queue = True
                    except json.JSONDecodeError:
                        # Malformed JSON - data error, remove from queue
                        logger.warning(f"Malformed JSON for queued data - removing from queue")
                        remove_from_queue = True

                    if remove_from_queue:
                        queue.pop(0)
                        save_queue(queue[-100:])
                        continue  # Try next item
                    # else: break was already called above

                else:
                    # Non-200 response (4xx/5xx) - stop retrying, exit thread
                    logger.error(f"Retry got {response.status_code} error - stopping retry thread")
                    break

            except Exception as e:
                # Network error or exception - stop retrying, exit thread
                logger.error(f"Retry failed with exception: {e} - stopping retry thread")
                break

    finally:
        with _retry_thread_lock:
            _retry_thread_running = False
        logger.debug("Retry thread stopped")


def retry_failed_transmissions():
    """Start background thread to retry queued failed transmissions"""
    global _retry_thread_running

    with _retry_thread_lock:
        if _retry_thread_running:
            logger.debug("Retry thread already running, skipping")
            return

        queue = load_queue()
        if not queue:
            logger.debug("Queue empty, no retry needed")
            return

        logger.debug(f"Starting retry thread for {len(queue)} queued items")
        _retry_thread_running = True

        thread = threading.Thread(target=_retry_queue_worker, daemon=True)
        thread.start()
