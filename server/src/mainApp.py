# Modified server/src/mainApp.py with Redis integration
import asyncio
import os
import sys
import time
import signal
import subprocess
import threading
from websocketUtils import WebsocketUtils
from dbUtils import DbUtils
from messageUtils import MessageUtils
from cryptographyUtils import CryptoUtils
from redisUtils import RedisManager  # Import the new Redis manager
from logConfig import logger
from envLoader import load_env

load_env()

# Global variables
client_process = None
shutdown_event = threading.Event()  # Used for clean shutdown


def get_encryption_password():
    secret_path = os.getenv("SECRET_PATH")
    if os.path.exists(secret_path):
        with open(secret_path, "r") as f:
            return f.read().strip()
    logger.error("Encryption password secret not found.")
    sys.exit(1)

def initialize_nym_client():
    """Checks if Nym client is already initialized, and initializes if necessary."""
    nym_client_id = os.getenv("NYM_CLIENT_ID")
    nym_client_dir = f"/root/.nym/clients/{nym_client_id}"

    if os.path.exists(nym_client_dir):
        logger.info("Existing Nym config found. Skipping init.")
    else:
        logger.info("No existing Nym config found. Initializing...")
        command = ["./nym-client", "init", "--id", nym_client_id, "--host", "0.0.0.0"]
        try:
            subprocess.run(command, check=True)
            logger.info("Nym client initialized successfully.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to initialize Nym client: {e}")
            sys.exit(1)

def start_client():
    """Starts the `nym-client` process without using a shell."""
    global client_process
    try:
        command = ["./nym-client", "run", "--id", os.getenv("NYM_CLIENT_ID")]
        client_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("Nym client started successfully.")

        # Wait for the client to initialize
        time.sleep(5)  # Allow the client time to start up before proceeding

    except Exception as e:
        logger.error(f"Failed to start Nym client: {e}")
        client_process = None

def monitor_client():
    """Monitors the Nym client output for errors and restarts if necessary."""
    global client_process
    while True:
        if client_process is None or client_process.poll() is not None:
            logger.error("Nym client crashed. Restarting in 10 seconds...")
            time.sleep(10)
            start_client()
            continue

        try:
            # Read output from stdout and stderr
            stdout, stderr = client_process.communicate(timeout=60)
            output = (stdout + stderr).decode()

            # Check if there's any error (any occurrence of "ERROR")
            if "ERROR" in output:
                logger.error(f"Error detected in client output: {output}")
                client_process.terminate()  # Restart on error
                time.sleep(2)  # Short wait before restarting
        except subprocess.TimeoutExpired:
            logger.info("Nym client is still running, no issues detected.")
        except Exception as e:
            logger.error(f"Unhandled error while monitoring Nym client: {e}")

def graceful_shutdown(signal_received, frame):
    """Handles shutdown signals (SIGINT & SIGTERM) to terminate processes cleanly."""
    logger.info("Graceful shutdown initiated. Sending Ctrl+C to Nym client...")
    shutdown_event.set()  # Signal the monitoring thread to stop

    if client_process is not None:
        client_process.send_signal(signal.SIGINT)  # Send SIGINT (Ctrl+C)
        logger.info("Waiting 5 seconds for Nym client to shut down gracefully...")
        time.sleep(5)  # Give it time to handle cleanup
        logger.info("Nym client shutdown complete.")

    sys.exit(0)

async def presence_heartbeat(redis_manager, database_manager):
    """
    Periodically checks and expires user presence.
    Also sends periodic heartbeats for the server's own status.
    """
    try:
        while not shutdown_event.is_set():
            # Get all users from the database
            all_users = database_manager.get_all_users()
            
            # Get all currently online users from Redis
            online_users = await redis_manager.get_all_online_users()
            
            # Log online user count
            logger.info(f"Presence heartbeat: {len(online_users)} users online")
            
            # Wait for next cycle
            await asyncio.sleep(60)  # Check every minute
    except Exception as e:
        logger.error(f"Error in presence heartbeat: {e}")

async def handle_redis_message(channel, data):
    """
    Handle messages received from Redis subscriptions.
    This function will be called when new messages arrive on subscribed channels.
    """
    try:
        logger.info(f"Redis message received on channel {channel}: {data}")
        # Add processing logic as needed
    except Exception as e:
        logger.error(f"Error handling Redis message: {e}")

async def main():
    """Main asynchronous function handling WebSocket communication."""
    password = get_encryption_password()

    websocket_url = os.getenv("WEBSOCKET_URL")
    db_path = os.getenv("DATABASE_PATH", "storage/nym_server.db")
    key_dir = os.getenv("KEYS_DIR", "storage/keys")
    redis_url = os.getenv("REDIS_URL")

    cryptography_utils = CryptoUtils(key_dir, password)
    database_manager = DbUtils(db_path)
    
    # Initialize Redis if URL is provided
    redis_manager = None
    if redis_url:
        try:
            redis_manager = RedisManager(redis_url)
            redis_connected = await redis_manager.connect()
            if redis_connected:
                logger.info("Redis connected successfully")
                # Subscribe to system channels
                await redis_manager.subscribe("system_events", handle_redis_message)
                # Start presence heartbeat task
                asyncio.create_task(presence_heartbeat(redis_manager, database_manager))
            else:
                logger.warning("Redis connection failed, continuing without Redis features")
                redis_manager = None
        except Exception as e:
            logger.error(f"Redis initialization error: {e}")
            redis_manager = None

    websocket_manager = WebsocketUtils(websocket_url)
    message_handler = MessageUtils(websocket_manager, database_manager, cryptography_utils, password, redis_manager)

    websocket_manager.set_message_callback(message_handler.processMessage)

    try:
        logger.info("Connecting to WebSocket...")
        await websocket_manager.connect()
        logger.info("Waiting for incoming messages...")

        while not shutdown_event.is_set():
            await asyncio.sleep(1)  # Prevent busy-waiting

    except asyncio.CancelledError:
        logger.info("Main coroutine was cancelled.")
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Closing gracefully...")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
    finally:
        logger.info("Closing connections...")
        if redis_manager:
            await redis_manager.close()
        await websocket_manager.close()
        database_manager.close()


if __name__ == "__main__":
    # Register SIGTERM and SIGINT handlers for clean shutdown
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)
    
    initialize_nym_client()

    # Start Nym client first
    start_client()

    # Start monitoring the Nym client in a separate thread
    monitoring_thread = threading.Thread(target=monitor_client, daemon=True).start()
    
    # Start the async WebSocket server
    try:
        asyncio.run(main())  # Run the main async function
    except KeyboardInterrupt:
        logger.info("Application interrupted by user.")
    except asyncio.CancelledError:
        logger.info("Application shutdown gracefully.")
