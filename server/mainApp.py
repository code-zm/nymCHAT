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


def print_msg_box(msg, indent=1, width=None, title=None):
    """Print message-box with optional title."""
    lines = msg.split('\n')
    space = " " * indent
    if not width:
        width = max(map(len, lines))
    box = f'╔{"═" * (width + indent * 2)}╗\n'  # upper_border
    if title:
        box += f'║{space}{title:<{width}}{space}║\n'  # title
        box += f'║{space}{"-" * len(title):<{width}}{space}║\n'  # underscore
    box += ''.join([f'║{space}{line:<{width}}{space}║\n' for line in lines])
    box += f'╚{"═" * (width + indent * 2)}╝'  # lower_border
    print(box)

def display_disclaimer():
    """Display a simple legal disclaimer at startup and require user confirmation."""
    msg = ( "This software is provided as-is, with no guarantees or warranties.\n"
"The authors are not responsible for any damages or legal consequences.\n"
"Use at your own risk."
    )
    print_msg_box(msg, indent=4, title = "TERMS & CONDITIONS")
    while True:
        user_input = input("Do you accept these terms? (Y/N): ").strip().lower()
        if user_input == 'y' or user_input == 'Y':
            break
        elif user_input == 'n' or user_input == 'N':
            print("Exiting application.")
            sys.exit(0)
        else:
            print("Invalid input. Please enter 'Y' to accept or 'N' to exit.")

def prompt_for_password():
    """Prompt the user for the encryption password with additional context and confirmation."""
    storage_dir = "storage"
    db_files = [f for f in os.listdir(storage_dir) if f.endswith(".db")]
    server_username = os.getenv("SERVER_USERNAME")  # Get the correct server user from env
    security_msg = (
        "This application uses ECC w/ SECP256R1.\n"
        "Your private key is encrypted using AES-256-GCM\n"
        "You must enter the correct password to unlock and use your private key."
    )
    print_msg_box(msg=security_msg, indent=2, title="Security Notice")
    if not db_files:
        while True:
            print("\nFirst-time setup detected!")
            print("You are generating a new encrypted key pair for secure communication.")
            print("Choose a strong password and **DO NOT FORGET IT**, as it cannot be recovered!")
            print("STORE SOMEWHERE SAFE, PREFERABLY OFFLINE")
            password = getpass.getpass("Enter a new encryption password: ")
            confirm_password = getpass.getpass("Re-enter the encryption password: ")
            
            if password == confirm_password:
                return password
            else:
                print("Passwords do not match. Please try again.")
    else:
        max_attempts = 6
        for attempt in range(max_attempts):
            password = getpass.getpass(f"Enter the key password for {server_username} (Attempt {attempt + 1}/{max_attempts}): ")
            cryptography_utils = CryptoUtils(os.getenv("KEYS_DIR", "storage/keys"), password)
            test_key_path = os.path.join(os.getenv("KEYS_DIR", "storage/keys"), f"{server_username}_private_key.enc")
            
            if os.path.exists(test_key_path):
                test_key = cryptography_utils.load_private_key(server_username)
                if test_key is not None:
                    return password
                else:
                    print("Incorrect password. Please try again.")
            else:
                return password  # No key exists yet, allow any password
        
        logger.warning("Password Verification Failed")
        sys.exit(1)
        
async def main():
    display_disclaimer()
    # Securely prompt for the key encryption password
    password = prompt_for_password()
    
    # Ensure all necessary environment variables are loaded
    websocket_url = os.getenv("WEBSOCKET_URL")
    db_path = os.getenv("DATABASE_PATH", "storage/nym_server.db")
    key_dir = os.getenv("KEYS_DIR", "storage/keys")
    server_username = os.getenv("SERVER_USERNAME")

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
