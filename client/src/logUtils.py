import logging
import os

# Configure logging
LOG_FILE = os.path.join(os.getcwd(), "storage", "app.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),  # Log to file
        logging.StreamHandler()  # Log to console
    ]
)

logger = logging.getLogger("AppLogger")

logging.getLogger("watchfiles").setLevel(logging.WARNING)
