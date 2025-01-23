# mainApp.py
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

    try:
        # Connect to WebSocket
        print("[INFO] Connecting to WebSocket...")
        await websocket_manager.connect()

        print("[INFO] Waiting for incoming messages...")

        while True:
            # Receive a message from the WebSocket
            received_message = await websocket_manager.receive()

            if received_message:
                print(f"[RECEIVED] {json.dumps(received_message, indent=2)}")
                # Process the message
                await message_handler.process_message(received_message)
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


