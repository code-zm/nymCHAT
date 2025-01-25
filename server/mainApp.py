import asyncio
import json
from websocketUtils import WebsocketUtils
from dbUtils import DbUtils
from messageUtils import MessageUtils

async def main():
    # Initialize components
    websocket_url = "ws://127.0.0.1:1977"
    db_path = "nym_server.db"

    websocket_manager = WebsocketUtils(websocket_url)
    database_manager = DbUtils(db_path)
    message_handler = MessageUtils(websocket_manager, database_manager)

    # Set the callback for processing WebSocket messages
    websocket_manager.set_message_callback(message_handler.processMessage)

    try:
        # Connect to WebSocket
        print("[INFO] Connecting to WebSocket...")
        await websocket_manager.connect()

        print("[INFO] Waiting for incoming messages...")

        # Keep the event loop running
        while True:
            await asyncio.sleep(1)  # Prevent busy-waiting

    except asyncio.CancelledError:
        print("[INFO] Main coroutine was cancelled.")
        # Perform any additional cleanup if necessary
        raise
    except KeyboardInterrupt:
        print("[INFO] Received KeyboardInterrupt. Closing gracefully...")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        # Clean up resources
        print("[INFO] Closing connections...")
        await websocket_manager.close()
        database_manager.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[INFO] Application interrupted by user.")
    except asyncio.CancelledError:
        print("[INFO] Application shutdown gracefully.")
