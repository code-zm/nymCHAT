import asyncio
import getpass
import os
import sys
from websocketUtils import WebsocketUtils
from dbUtils import DbUtils
from messageUtils import MessageUtils
from cryptographyUtils import CryptoUtils
from logConfig import logger
from envLoader import load_env

load_env()


def get_encryption_password():
    secret_path = os.getenv("SECRET_PATH")
    if os.path.exists(secret_path):
        with open(secret_path, "r") as f:
            return f.read().strip()
    logger.error("Encryption password secret not found.")
    sys.exit(1)
        
async def main():
    # Securely prompt for the key encryption password
    password = get_encryption_password()
    
    # Ensure all necessary environment variables are loaded
    websocket_url = os.getenv("WEBSOCKET_URL")
    db_path = os.getenv("DATABASE_PATH", "storage/nym_server.db")
    key_dir = os.getenv("KEYS_DIR", "storage/keys")

    # Initialize cryptography utility
    cryptography_utils = CryptoUtils(key_dir, password)
      # Now, initialize database manager with encryption
    database_manager = DbUtils(db_path, cryptography_utils)

    # Initialize WebSocket manager and message handler
    websocket_manager = WebsocketUtils(websocket_url)
    message_handler = MessageUtils(websocket_manager, database_manager, cryptography_utils, password)

    websocket_manager.set_message_callback(message_handler.processMessage)

    try:
        logger.info("Connecting to WebSocket...")
        await websocket_manager.connect()
        logger.info("Waiting for incoming messages...")

        while True:
            await asyncio.sleep(1)  # Prevent busy-waiting

    except asyncio.CancelledError:
        logger.info("Main coroutine was cancelled.")
        raise
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Closing gracefully...")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
    finally:
        logger.info("Closing connections...")
        await websocket_manager.close()
        database_manager.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user.")
    except asyncio.CancelledError:
        logger.info("Application shutdown gracefully.")
