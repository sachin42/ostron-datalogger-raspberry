import pytz
import logging
from logging.handlers import RotatingFileHandler

# File paths
SENSORS_FILE = 'sensors.json'
QUEUE_FILE = 'failed_queue.json'

# Time utilities
IST = pytz.timezone("Asia/Kolkata")

# Set up rotating file handler
handler = RotatingFileHandler('datalogger.log', maxBytes=10*1024*1024, backupCount=5)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)
