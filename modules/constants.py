import pytz
import logging
import os
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Load .env to check dev mode for logger setup
load_dotenv()
dev_mode = os.getenv('DEV_MODE', 'false').lower() in ('true', '1', 'yes')

# File paths
SENSORS_FILE = 'sensors.json'
QUEUE_FILE = 'failed_queue.json'

# Time utilities
IST = pytz.timezone("Asia/Kolkata")

# Set up rotating file handler
handler = RotatingFileHandler('datalogger.log', maxBytes=10*1024*1024, backupCount=5)
handler.setLevel(logging.DEBUG if dev_mode else logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if dev_mode else logging.INFO)
logger.addHandler(handler)
