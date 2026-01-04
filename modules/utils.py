import time
from datetime import datetime
from .constants import IST, LOCK_FILE, PLATFORM_WINDOWS

# Import platform-specific locking
if PLATFORM_WINDOWS:
    import msvcrt
else:
    import fcntl


def acquire_lock(lock_file: str = LOCK_FILE, timeout: int = 10):
    """Context manager for cross-platform file locking"""
    class FileLock:
        def __init__(self, filename, timeout):
            self.filename = filename
            self.timeout = timeout
            self.file = None

        def __enter__(self):
            start_time = time.time()
            while True:
                try:
                    self.file = open(self.filename, 'w')
                    if PLATFORM_WINDOWS:
                        # Windows locking
                        msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        # Unix locking
                        fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return self
                except (IOError, OSError):
                    if self.file:
                        self.file.close()
                    if time.time() - start_time > self.timeout:
                        raise TimeoutError("Could not acquire lock")
                    time.sleep(0.1)

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.file:
                try:
                    if PLATFORM_WINDOWS:
                        msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
                except:
                    pass
                self.file.close()

    return FileLock(lock_file, timeout)


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
