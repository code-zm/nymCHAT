import logging
import os
from envLoader import load_env

load_env()

# Configure logging
LOG_FILE = os.getenv("LOG_FILE_PATH", "storage/app.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),  # Log to file
        logging.StreamHandler()  # Log to console
    ]
)

logger = logging.getLogger("AppLogger")


