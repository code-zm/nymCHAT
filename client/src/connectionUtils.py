import json
import asyncio
import os
from async_ffi import PyMixnetClient
from logUtils import logger

class MixnetConnectionClient:
    def __init__(self):
        self.client = None
        self.websocket_url = None
        
        # Initialize environment-based configuration
        self.nym_client_host = os.getenv("NYM_CLIENT_HOST", "")
        self.nym_client_port = os.getenv("NYM_CLIENT_PORT", "1977")
        
        # Connection status tracking
        self.connected = False
        self.connection_attempts = 0
        self.max_retries = 3
        self.retry_delay = 2  # seconds

    async def init(self):
        """
        Initialize mixnet client with retry logic for containerized environments.
        
        The PyMixnetClient.create() doesn't accept connection parameters directly,
        so we rely on environment variables being correctly set at container startup.
        """
        self.connection_attempts = 0
        errors = []
        
        while self.connection_attempts < self.max_retries:
            try:
                self.connection_attempts += 1
                logger.info(f"Initializing Mixnet client (attempt {self.connection_attempts})")
                
                # PyMixnetClient doesn't accept direct host/port configuration,
                # so we must ensure WEBSOCKET_URL env var is set correctly
                self.client = await PyMixnetClient.create()
                self.connected = True
                logger.info("Mixnet client initialized successfully")
                return True
                
            except Exception as e:
                error = f"Mixnet client initialization failed: {str(e)}"
                logger.warning(error)
                errors.append(error)
                
                if self.connection_attempts < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                    
        # All attempts failed
        logger.error(f"Failed to initialize Mixnet client after {self.connection_attempts} attempts")
        for err in errors:
            logger.error(f"  - {err}")
            
        raise ConnectionError(f"Failed to initialize Mixnet client: Max retries ({self.max_retries}) exceeded")

    async def get_nym_address(self):
        """
        Get client's Nym address with automatic reconnection.
        """
        if not self.client:
            await self.init()
            
        try:
            return await self.client.get_nym_address()
        except Exception as e:
            logger.error(f"Error getting Nym address: {e}")
            # Try to reconnect once
            await self.init()
            return await self.client.get_nym_address()

    async def send_message(self, message):
        """
        Send message with auto-reconnect on failure.
        """
        if not self.client:
            await self.init()
            
        recipient = message.get("recipient")
        msg = message.get("message")
        
        if not recipient or not msg:
            raise ValueError("Both 'recipient' and 'message' must be provided")
            
        try:
            await self.client.send_message(recipient, msg)
            
        except Exception as e:
            logger.error(f"Send message failed: {e}")
            # Try to reconnect and send again
            await self.init()
            await self.client.send_message(recipient, msg)

    async def set_message_callback(self, callback):
        """
        Set callback function with auto-reconnect on failure.
        """
        if not self.client:
            await self.init()
            
        try:
            await self.client.set_message_callback(callback)
            
        except Exception as e:
            logger.error(f"Set callback failed: {e}")
            # Try to reconnect and set callback again
            await self.init()
            await self.client.set_message_callback(callback)

    async def receive_messages(self):
        """
        Start receiving messages with auto-reconnect capability.
        """
        if not self.client:
            await self.init()
            
        try:
            logger.info("Starting message reception loop")
            await self.client.receive_messages()
            
        except Exception as e:
            logger.error(f"Receive messages loop failed: {e}")
            # Try to restart the reception loop
            await self.init()
            await self.client.receive_messages()

    async def shutdown(self):
        """
        Shut down client safely.
        """
        if self.client:
            try:
                await self.client.shutdown()
                self.client = None
                self.connected = False
                logger.info("Mixnet client shut down successfully")
                
            except Exception as e:
                logger.error(f"Error shutting down client: {e}")
                # Force cleanup
                self.client = None
                self.connected = False

