import json
import os
import time
import requests
from typing import List

from .constants import QUEUE_FILE, logger
from .config import get_env
from .crypto import generate_signature


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
            json.dump(queue, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving queue: {e}")


def retry_failed_transmissions() -> int:
    """Retry queued failed transmissions after successful send"""
    queue = load_queue()
    if not queue:
        return 0

    successful = 0
    remaining = []

    endpoint = get_env('endpoint', "https://cems.cpcb.gov.in/v1.0/industry/data")
    token_id = get_env('token_id', '')
    public_key_pem = get_env('public_key', '')
    device_id = get_env('device_id', '')

    for item in queue:
        # Check if data is too old (backdate limit 7 days)
        current_ts = int(time.time() * 1000)
        if 'aligned_ts' in item and (current_ts - item['aligned_ts']) > 7 * 24 * 60 * 60 * 1000:
            logger.info(f"Skipping old queued data from {item['timestamp']}")
            continue

        try:
            # Regenerate signature with current time
            signature = generate_signature(token_id, public_key_pem)

            headers = {
                "Content-Type": "text/plain",
                "X-Device-Id": device_id,
                "signature": signature
            }

            response = requests.post(endpoint, data=item['encrypted_payload'],
                                     headers=headers, timeout=20)
            logger.info(f"Retry send status: {response.status_code} - {response.text}")

            success = False
            if response.status_code == 200:
                try:
                    data = json.loads(response.text.strip())
                    success = data.get('msg') == 'success' and data.get('status') == 1
                except json.JSONDecodeError:
                    pass

            if success:
                successful += 1
                logger.info(f"Successfully sent queued data from {item['timestamp']}")
            else:
                remaining.append(item)

        except Exception as e:
            logger.error(f"Retry failed: {e}")
            remaining.append(item)

    # Keep only last 100 failed items to prevent unbounded growth
    save_queue(remaining[-100:])
    return successful
