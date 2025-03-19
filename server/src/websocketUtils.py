import asyncio
import json
import os
import websockets
from logConfig import logger
from envLoader import load_env

load_env()

class WebsocketUtils:
    def __init__(self, server_url=None):
        # Primary URL from environment with explicit fallback chain
        self.server_url = server_url or os.getenv("WEBSOCKET_URL")
        
        # Failover targets in priority order
        self.fallback_targets = [
            os.getenv("NYM_CLIENT_HOST", "nym-client"),  # Container name in Docker network
        ]
        self.fallback_port = os.getenv("NYM_CLIENT_PORT", "1977")
        
        self.websocket = None
        self.message_callback = None
        self.address = None
        self.connection_attempts = 0
        self.reconnect_delay = 2  # seconds between connection attempts

    async def connect(self):
        """Establish WebSocket connection with failover support"""
        connection_errors = []
        urls_to_try = []
        
        # Start with explicit URL if provided
        if self.server_url:
            urls_to_try.append(self.server_url)
        
        # Add fallback URLs with port specification
        for target in self.fallback_targets:
            urls_to_try.append(f"ws://{target}:{self.fallback_port}")
        
        # Deduplicate URLs while preserving priority order
        urls_to_try = list(dict.fromkeys(urls_to_try))
        
        for url in urls_to_try:
            try:
                logger.info(f"Attempting connection to: {url}")
                self.connection_attempts += 1
                
                self.websocket = await websockets.connect(url, ping_interval=30)
                await self.websocket.send(json.dumps({"type": "selfAddress"}))
                response = await self.websocket.recv()
                data = json.loads(response)
                
                self.address = data.get("address")
                if not self.address:
                    logger.error(f"Empty address received from {url}")
                    raise ValueError("Invalid Nym address (empty)")
                    
                logger.info(f"Connected to {url}. Nym Address: {self.address}")
                
                # Connection successful, save address to file
                self._save_address_to_file()
                
                # Start message loop and return on success
                asyncio.create_task(self.receive_messages())
                return True
                
            except (websockets.exceptions.InvalidURI, ValueError) as e:
                # Configuration errors - log and continue to next endpoint
                logger.error(f"Invalid URI or value: {url} - {str(e)}")
                connection_errors.append(f"{url}: {str(e)}")
                
            except (ConnectionRefusedError, OSError, websockets.exceptions.ConnectionClosedError) as e:
                # Network errors - try next endpoint
                logger.warning(f"Connection to {url} failed: {str(e)}")
                connection_errors.append(f"{url}: {str(e)}")
                await asyncio.sleep(self.reconnect_delay)
                
            except Exception as e:
                # Unexpected errors
                logger.error(f"Unexpected error connecting to {url}: {str(e)}")
                connection_errors.append(f"{url}: {str(e)}")
        
        # All connection attempts failed
        logger.error(f"Failed to connect to any Nym client endpoint after {self.connection_attempts} attempts")
        for err in connection_errors:
            logger.error(f"  - {err}")
        raise ConnectionError(f"All {len(urls_to_try)} connection attempts failed")

    def _save_address_to_file(self):
        """Write Nym address to shared file"""
        try:
            shared_dir = "/app/shared"
            os.makedirs(shared_dir, exist_ok=True)
            file_path = os.path.join(shared_dir, "nym_address.txt")
            
            with open(file_path, "w") as f:
                f.write(self.address)
                
            logger.info(f"Nym address saved to {file_path}")
        except IOError as e:
            logger.error(f"Failed to write address to file: {e}")

    async def receive_messages(self):
        """Message reception loop with auto-reconnect"""
        try:
            while True:
                try:
                    raw_message = await self.websocket.recv()
                    message_data = json.loads(raw_message)

                    # Call the callback for processing
                    if self.message_callback:
                        await self.message_callback(message_data)
                    else:
                        logger.warning("Message received but no callback set")
                        
                except websockets.exceptions.ConnectionClosed as e:
                    logger.warning(f"WebSocket connection closed: {e}")
                    # Attempt reconnection
                    await asyncio.sleep(self.reconnect_delay)
                    await self.connect()
                    
        except Exception as e:
            logger.error(f"Fatal error in message reception loop: {e}")
            
    async def send(self, message):
        """Send a message with auto-reconnect on failure"""
        try:
            if not self.websocket:
                logger.warning("No active websocket, attempting reconnection")
                await self.connect()
                
            if isinstance(message, dict):
                message = json.dumps(message)
                
            await self.websocket.send(message)
            
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection closed while sending, attempting reconnect")
            await self.connect()
            
            # Retry once after reconnection
            if isinstance(message, dict):
                message = json.dumps(message)
            await self.websocket.send(message)
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise

    async def close(self):
        """Close the websocket connection cleanly"""
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        else:
            logger.warning("No active connection to close")

    def set_message_callback(self, callback):
        """Set callback function for message processing"""
        self.message_callback = callback
