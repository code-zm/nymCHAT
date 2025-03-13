import subprocess
import time
import logging
import os
import signal
from envLoader import load_env

load_env()

# Set up logging
logging.basicConfig(filename="client_monitor.log", level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Command to run the server binary
server_command = f'./nym-client run --id {os.getenv("NYM_CLIENT_ID", "default-id")}'

# Function to start the client binary and return the process
def start_client():
    try:
        process = subprocess.Popen(server_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info("Client started successfully.")
        return process
    except Exception as e:
        logging.error(f"Failed to start client: {e}")
        return None

# Function to monitor the client output for errors
def monitor_client(process):
    try:
        # Read output from stdout and stderr
        stdout, stderr = process.communicate(timeout=60)  # Set timeout to prevent hanging indefinitely
        output = (stdout + stderr).decode()

        # Check if there's any error (any occurrence of "ERROR")
        if "ERROR" in output:
            logging.error(f"Error detected in client output: {output}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logging.warning("Client is still running, no issues detected.")
        return True
    except Exception as e:
        logging.error(f"Unhandled error while monitoring client: {e}")
        return False

# Graceful shutdown handler
def graceful_shutdown(signal, frame):
    logging.info("Graceful shutdown initiated. Terminating the client...")
    # Kill the process if it's running
    if client_process is not None:
        client_process.terminate()
        logging.info("Terminate signal sent. Waiting for the client to clean up...")
        time.sleep(10)  # Allow time for the binary to handle cleanup (adjust as needed)
        logging.info("Shutdown complete.")
    exit(0)

# Main function to manage the client lifecycle
def monitor_and_restart_client():
    global client_process

    # Set up the signal handler for graceful shutdown
    signal.signal(signal.SIGINT, graceful_shutdown)  # Catch Ctrl+C

    while True:
        logging.info("Starting client monitoring...")
        
        # Start the client
        client_process = start_client()

        if not client_process:
            logging.error("Client failed to start, retrying...")
            time.sleep(10)  # Wait before trying to restart
            continue

        # Monitor the client
        while client_process.poll() is None:  # While the process is running
            time.sleep(5)  # Check every 5 seconds
            if not monitor_client(client_process):
                logging.info("Detected error, restarting the client...")
                client_process.terminate()  # Terminate the current process
                time.sleep(2)  # Give it a moment to shut down
                break  # Exit the inner loop to restart the client

        # Wait a bit before restarting if necessary
        time.sleep(10)

if __name__ == "__main__":
    monitor_and_restart_client()

