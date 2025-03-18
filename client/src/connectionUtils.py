import json
from async_ffi import PyMixnetClient
from logUtils import logger

class MixnetConnectionClient:
    def __init__(self):
        self.client = None  # Will be initialized asynchronously

    async def init(self):
        """
        Asynchronously initialize the mixnet client.
        """
        self.client = await PyMixnetClient.create()

    async def get_nym_address(self):
        """
        Asynchronously retrieve the client's Nym address.
        """
        return await self.client.get_nym_address()

    async def send_message(self, message):
        """
        Send a message using the async mixnet FFI.
        Expects `message` to be a dict with at least 'recipient' and 'message' keys.
        """
        recipient = message.get("recipient")
        msg = message.get("message")
        if not recipient or not msg:
            raise ValueError("Both 'recipient' and 'message' must be provided.")
        await self.client.send_message(recipient, msg)

    async def set_message_callback(self, callback):
        """
        Set a callback function for incoming messages.
        """
        await self.client.set_message_callback(callback)

    async def receive_messages(self):
        """
        Start receiving messages from the Mixnet.
        """
        logger.info("STARTED MESSAGE RECEIVING LOOP")
        await self.client.receive_messages()  # Ensure this is awaited properly

    async def shutdown(self):
        """
        Asynchronously shut down the mixnet client.
        """
        await self.client.shutdown()
