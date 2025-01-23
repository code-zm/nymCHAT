# websocketManager.py
import asyncio
import json
from websockets import connect

class WebsocketUtils:
    def __init__(self, websocketUrl="ws://127.0.0.1:1977"):
        self.websocketUrl = websocketUrl
        self.websocket = None

    async def connect(self):
        try:
            self.websocket = await connect(self.websocketUrl)
            print("Connected to WebSocket.")
        except Exception as e:
            print(f"WebSocket connection error: {e}")

    async def send(self, message):
        if self.websocket:
            print("Sending message:", message)
            await self.websocket.send(json.dumps(message))

    async def receive(self):
        try:
            if self.websocket:
                message = await self.websocket.recv()
                return json.loads(message)
        except asyncio.CancelledError:
            # Gracefully handle the cancellation
            print("[INFO] receive() coroutine was cancelled.")
            raise  # Reraise the exception so the cancellation propagates correctly
        except Exception as e:
            print(f"Error receiving message: {e}")


    async def close(self):
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                print(f"Error closing WebSocket: {e}")
            finally:
                self.websocket = None

