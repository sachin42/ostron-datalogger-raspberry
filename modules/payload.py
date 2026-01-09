import json
from typing import Tuple
from .config import get_env
from .utils import get_aligned_timestamp_ms


def build_plain_payload(sensors: dict, device_id: str, station_id: str) -> Tuple[str, int]:
    """Build plain JSON payload with aligned timestamps and 'U' flag"""
    params = []

    # Use 1-minute alignment in DEV_MODE, 15-minute in production
    dev_mode = get_env('dev_mode', False)
    alignment_minutes = 1 if dev_mode else 15
    ts = get_aligned_timestamp_ms(alignment_minutes)

    for param, data in sensors.items():
        params.append({
            "parameter": param,
            "value": data['value'],
            "unit": data['unit'],
            "timestamp": ts,
            "flag": "U"
        })

    payload = {
        "data": [
            {
                "stationId": station_id,
                "device_data": [
                    {
                        "deviceId": device_id,
                        "params": params
                    }
                ]
            }
        ]
    }

    return json.dumps(payload, separators=(",", ":")), ts
