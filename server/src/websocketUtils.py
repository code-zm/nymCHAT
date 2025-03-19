import asyncio
import json
import os
import websockets
from logConfig import logger
from envLoader import load_env

load_env()

class WebsocketUtils:
    def __init__(self, server_url=None):
        self.server_url = server_url or os.getenv("WEBSOCKET_URL")
        self.websocket = None
        self.message_callback = None  # Callback for processing messages
        self.address = None # store the address

    async def connect(self):
        """Establish a WebSocket connection with the Nym client."""
        try:
            self.websocket = await websockets.connect(self.server_url)
            await self.websocket.send(json.dumps({"type": "selfAddress"}))
            response = await self.websocket.recv()
            data = json.loads(response)
            
            # Store address and validate
            self.address = data.get("address")
            if not self.address:
                logger.error("Failed to retrieve valid Nym address")
                raise ValueError("Empty or invalid Nym address received")
                
            logger.info(f"Connected to WebSocket. Your Nym Address: {self.address}")
            
            # Save to file with proper error handling
            try:
               # project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
               
                ### DIRTY HACKS
                ### SEE COMMENT BELOW

                shared_dir = "/app/shared"
                os.makedirs(shared_dir, exist_ok=True)
                file_path = os.path.join(shared_dir, "nym_address.txt")
                # @gyrusdentatus
                #file_path = os.path.join(project_root, "nym_address.txt")
                #
                # Save that fucker to shared mount for developer QoL improvement 
                # might wanna change this back to the above later if it's 
                # not really needed. Not that it's a security issue but 
                # The lesser space to fuck up the better, AMIRITE??? ;d 
               # file_path = os.path.join(project_root, "shared", "nym_address.txt")
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, "w") as f:
                    f.write(self.address)
                    
                logger.info(f"Nym address saved to {file_path}")
            except IOError as e:
                logger.error(f"Failed to write address to file: {e}")
                # Continue execution - failure to write file shouldn't crash the server

            # Start listening for incoming messages
            await self.receive_messages()
        except Exception as e:
            logger.error(f"Connection error: {e}")
            raise  # Re-raise to signal failure up the stack

    async def receive_messages(self):
        """Listen for incoming messages and forward them to the callback."""
        try:
            while True:
                raw_message = await self.websocket.recv()
                logger.info("Message received")
                message_data = json.loads(raw_message)

                # Call the callback for further processing
                if self.message_callback:
                    await self.message_callback(message_data)
                else:
                    logger.warning("No callback set for processing messages.")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection closed by the server.")
        except Exception as e:
            logger.error(f"Error while receiving messages: {e}")
            
    async def send(self, message):
        """Send a message through the WebSocket."""
        try:
            if isinstance(message, dict):
                message = json.dumps(message)
            await self.websocket.send(message)
            logger.info("Message sent")
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def close(self):
        """Close the websocket connection."""
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("Websocket connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        else:
            logger.warning("Websocket connection is not established")

    def set_message_callback(self, callback):
        """Set the callback function for processing received messages."""
        self.message_callback = callback
