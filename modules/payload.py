import json

from .utils import get_aligned_timestamp_ms


def build_plain_payload(sensors: dict, device_id: str, station_id: str) -> str:
    """Build plain JSON payload with aligned timestamps and 'U' flag"""
    params = []
    ts = get_aligned_timestamp_ms()

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

    return json.dumps(payload, separators=(",", ":"))
