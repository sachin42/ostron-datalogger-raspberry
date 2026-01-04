import pytz
import logging
from logging.handlers import RotatingFileHandler

# File paths
CONFIG_FILE = 'config.json'
QUEUE_FILE = 'failed_queue.json'
LOCK_FILE = 'config.lock'

# Time utilities
IST = pytz.timezone("Asia/Kolkata")

# Cross-platform file locking
try:
    import fcntl
    PLATFORM_WINDOWS = False
except ImportError:
    import msvcrt
    PLATFORM_WINDOWS = True

# Set up rotating file handler
handler = RotatingFileHandler('datalogger.log', maxBytes=10*1024*1024, backupCount=5)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)
