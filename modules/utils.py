from datetime import datetime
from .constants import IST


def get_aligned_timestamp_ms() -> int:
    """Get timestamp aligned to 15-minute intervals"""
    now = datetime.now(IST)
    aligned_minute = (now.minute // 15) * 15
    aligned = now.replace(minute=aligned_minute, second=0, microsecond=0)
    return int(aligned.timestamp() * 1000)


def get_signature_timestamp() -> str:
    """Get formatted timestamp for signature"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def validate_timestamp(ts_ms: int) -> bool:
    """Validate timestamp according to server rules"""
    now = datetime.now(IST)
    now_ms = int(now.timestamp() * 1000)

    # Backdate limit: older than 7 days not accepted
    if now_ms - ts_ms > 7 * 24 * 60 * 60 * 1000:
        return False

    # Future date not allowed
    if ts_ms > now_ms:
        return False

    # Check alignment to 15 min
    dt = datetime.fromtimestamp(ts_ms / 1000, IST)
    if dt.minute % 15 != 0 or dt.second != 0 or dt.microsecond != 0:
        return False

    return True
