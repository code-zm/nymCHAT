import asyncio
from websocketUtils import WebsocketUtils
from dbUtils import DbUtils
from messageUtils import MessageUtils
from cryptographyUtils import CryptoUtils
from logConfig import logger
from envLoader import load_env
import os

load_env()

async def main():
    # Initialize components
    websocket_url = os.getenv("WEBSOCKET_URL")
    db_path = os.getenv("DATABASE_PATH")
    key_dir = os.getenv("KEYS_DIR")

    websocket_manager = WebsocketUtils(websocket_url)
    database_manager = DbUtils(db_path)
    cryptography_utils = CryptoUtils(key_dir)  # Initialize CryptoUtils
    message_handler = MessageUtils(websocket_manager, database_manager, cryptography_utils)  # Message handler uses CryptoUtils internally

    # Set the callback for processing WebSocket messages
    websocket_manager.set_message_callback(message_handler.processMessage)

    try:
        # Connect to WebSocket
        logger.info("Connecting to WebSocket...")
        await websocket_manager.connect()

        logger.info("Waiting for incoming messages...")

        # Keep the event loop running
        while True:
            await asyncio.sleep(1)  # Prevent busy-waiting

    except asyncio.CancelledError:
        logger.info("Main coroutine was cancelled.")
        # Perform any additional cleanup if necessary
        raise
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Closing gracefully...")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
    finally:
        # Clean up resources
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
