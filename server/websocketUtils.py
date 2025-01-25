import asyncio
import json
import websockets


class WebsocketUtils:
    def __init__(self, server_url="ws://127.0.0.1:1977"):
        self.server_url = server_url
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
            print("Connected to WebSocket. Your Nym Address:", self_address)

            # Start listening for incoming messages
            await self.receive_messages()
        except Exception as e:
            print("Connection error:", e)

    async def receive_messages(self):
        """Listen for incoming messages and forward them to the callback."""
        try:
            while True:
                raw_message = await self.websocket.recv()
                message_data = json.loads(raw_message)

                # Call the callback for further processing
                if self.message_callback:
                    await self.message_callback(message_data)
                else:
                    print(f"[WARNING] No callback set for processing messages. Received: {message_data}")
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed by the server.")
        except Exception as e:
            print(f"Error while receiving messages: {e}")

    async def send(self, message):
        """Send a message through the WebSocket."""
        try:
            if isinstance(message, dict):
                # Convert the dictionary to a JSON string
                message = json.dumps(message)
            await self.websocket.send(message)
            print(f"Message sent: {message}")
        except Exception as e:
            print(f"Error sending message: {e}")

    def set_message_callback(self, callback):
        """Set the callback function for processing received messages."""
        self.message_callback = callback
