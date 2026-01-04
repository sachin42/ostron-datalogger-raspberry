import json
from datetime import datetime

from .constants import IST
from .utils import get_aligned_timestamp_ms


def build_plain_payload(sensors: dict, device_id: str, station_id: str,
                        flag: str = "U", align: bool = True) -> str:
    """Build plain JSON payload"""
    params = []
    if align:
        ts = get_aligned_timestamp_ms()
    else:
        ts = int(datetime.now(IST).timestamp() * 1000)
    for param, data in sensors.items():
        params.append({
            "parameter": param,
            "value": data['value'],
            "unit": data['unit'],
            "timestamp": ts,
            "flag": flag
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
    return json.dumps(payload, separators=(",", ":"))
