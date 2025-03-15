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

    async def connect(self):
        """Establish a WebSocket connection with the Nym client."""
        try:
            self.websocket = await websockets.connect(self.server_url)
            await self.websocket.send(json.dumps({"type": "selfAddress"}))
            response = await self.websocket.recv()
            data = json.loads(response)
            self_address = data.get("address")
            logger.info(f"Connected to WebSocket. Your Nym Address: {self_address}")

            # Start listening for incoming messages
            await self.receive_messages()
        except Exception as e:
            logger.error(f"Connection error: {e}")

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
                # Convert the dictionary to a JSON string
                message = json.dumps(message)
            await self.websocket.send(message)
            logger.info("Message sent")
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    def set_message_callback(self, callback):
        """Set the callback function for processing received messages."""
        self.message_callback = callback
