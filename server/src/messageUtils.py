# server/src/messageUtils.py with Redis integration
import json
import secrets
import os
import re
import time
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature, decode_dss_signature
from cryptographyUtils import CryptoUtils
from envLoader import load_env
from logConfig import logger

load_env()

class MessageUtils:
    NONCES = {}  # Temporary storage for nonces
    PENDING_USERS = {}  # Temporary storage for user details during registration

    def __init__(self, websocketManager, databaseManager, crypto_utils, password, redis_manager=None):
        NYM_CLIENT_ID = os.getenv("NYM_CLIENT_ID")
        SERVER_KEY_PATH = os.getenv("KEYS_DIR")

        self.websocketManager = websocketManager
        self.databaseManager = databaseManager
        self.cryptoUtils = CryptoUtils(SERVER_KEY_PATH, password)
        self.redis_manager = redis_manager  # Add Redis manager

        private_key_path = os.path.join(os.getenv("KEYS_DIR"), f"{NYM_CLIENT_ID}_private_key.enc")

        # Ensure the server's key pair exists
        if not os.path.exists(private_key_path):
            self.cryptoUtils.generate_key_pair(NYM_CLIENT_ID)
            logger.info("Init - Server key pair generated.")

    @staticmethod
    def is_valid_username(username):
        """Validates that the username contains only letters, numbers, '-', or '_'"""
        return bool(re.fullmatch(r"[A-Za-z0-9_-]+", username))

    async def processMessage(self, messageData):
        messageType = messageData.get("type")

        if messageType == "received":
            await self.processReceivedMessage(messageData)
        else:
            logger.error(f"processMessaage - Unknown message type :( | {messageType}")

    async def processReceivedMessage(self, messageData):
        encapsulatedJson = messageData.get("message")
        senderTag = messageData.get("senderTag")

        try:
            encapsulatedData = json.loads(encapsulatedJson)
            action = encapsulatedData.get("action")

            if action == "query":
                await self.handleQuery(encapsulatedData, senderTag)
            elif action == "register":
                await self.handleRegister(encapsulatedData, senderTag)
            elif action == "login":
                await self.handleLogin(encapsulatedData, senderTag)
            elif action == "registrationResponse":
                await self.handleRegistrationResponse(encapsulatedData, senderTag)
            elif action == "update":
                await self.handleUpdate(encapsulatedData, senderTag)
            elif action == "send":
                await self.handleSend(encapsulatedData, senderTag)
            elif action == "sendGroup":
                await self.handleSendGroup(encapsulatedData, senderTag)
            elif action == "createGroup":
                await self.handleCreateGroup(encapsulatedData, senderTag)
            elif action == "inviteGroup":
                await self.handleSendInvite(encapsulatedData, senderTag)
            elif action == "loginResponse":
                await self.handleLoginResponse(encapsulatedData, senderTag)
            elif action == "presenceUpdate":
                await self.handlePresenceUpdate(encapsulatedData, senderTag)
            else:
                logger.error(f"processReceivedMessage - Unknown encapsulated action :( | {action}")
        except json.JSONDecodeError as e:
            logger.error(f"processReceivedMessage - Decoding JSON :( | {e}")

    async def handleSend(self, messageData, senderTag):
        """
        Handle a direct 'send' message request from a client.
        """

        content_str = messageData.get("content")
        signature = messageData.get("signature")

        # Basic validation
        if not content_str or not signature:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: missing 'content' or 'signature'",
                action="sendResponse",
                context="chat"
            )
            logger.warning("handleSend - missing content or signature :(")
            return

        # Parse the inner JSON for actual message details.
        try:
            content_dict = json.loads(content_str)
        except json.JSONDecodeError:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: invalid JSON in content",
                action="sendResponse",
                context="chat"
            )
            logger.warning("handleSend - invalid JSON :(")
            return

        # Extract sender and recipient usernames.
        sender_username = content_dict.get("sender")
        recipient_username = content_dict.get("recipient")
        if not sender_username or not recipient_username:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: missing 'sender' or 'recipient' field in message content",
                action="sendResponse",
                context="chat"
            )
            logger.warning("handleSend - missing sender/recipient :(")
            return

        # Look up the sender by username.
        senderRecord = self.databaseManager.getUserByUsername(sender_username)
        if not senderRecord:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: unrecognized sender username",
                action="sendResponse",
                context="chat"
            )
            logger.warning("handleSend - could not find sender in DB :(")
            return

        # Extract sender details from the database.
        dbSenderTag = senderRecord[2]
        dbPublicKey = senderRecord[1]

        # Verify the signature using the sender's public key.
        if not self.cryptoUtils.verify_signature(dbPublicKey, content_str, signature):
            await self.sendEncapsulatedReply(
                senderTag,
                "error: invalid signature",
                action="sendResponse",
                context="chat"
            )
            logger.warning("handleSend - invalid signature :(")
            return

        # Check if the senderTag has changed.
        if dbSenderTag != senderTag:
            self.databaseManager.updateUserField(sender_username, "senderTag", senderTag)

        # Look up the recipient by username.
        targetUser = self.databaseManager.getUserByUsername(recipient_username)
        if not targetUser:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: recipient not found",
                action="sendResponse",
                context="chat"
            )
            logger.warning("handleSend - could not find recipient in DB :(")
            return

        # Extract recipient senderTag.
        targetSenderTag = targetUser[2]

        # Build the forward payload.
        forwardPayload = {
            "sender": sender_username,
            "body": content_dict.get("body")
        }
        # Include sender's public key if present.
        if "senderPublicKey" in content_dict:
            forwardPayload["senderPublicKey"] = content_dict["senderPublicKey"]

        # Forward the message to the recipient.
        await self.sendEncapsulatedReply(
            targetSenderTag,
            json.dumps(forwardPayload),
            action="incomingMessage",
            context="chat"
        )

        # Publish notification to Redis if available
        if self.redis_manager and self.redis_manager.connection_status == "connected":
            notification = {
                "type": "new_message",
                "sender": sender_username,
                "recipient": recipient_username,
                "timestamp": time.time(),
            }
            channel = f"notifications:{recipient_username}"
            await self.redis_manager.publish(channel, notification)
            logger.info(f"Published message notification to {channel}")

        # Confirm success to the sender.
        await self.sendEncapsulatedReply(
            senderTag,
            "success",
            action="sendResponse",
            context="chat"
        )

    async def handleLogin(self, messageData, senderTag):
        """
        Handle the login request from the client.
        """
        username = messageData.get("usernym")

        if not username:
            await self.sendEncapsulatedReply(senderTag, "error: missing username", action="challengeResponse", context="login")
            logger.warning("handleLogin - missing username :(")
            return

        user = self.databaseManager.getUserByUsername(username)
        if not user:
            await self.sendEncapsulatedReply(senderTag, "error: user not found", action="challengeResponse", context="login")
            logger.warning("handleLogin - user not found in DB :(")
            return

        # Generate a nonce and store it
        nonce = secrets.token_hex(16)
        self.NONCES[senderTag] = (username, user[1], nonce)  # user[1] is the public key

        # Send the challenge to the client
        await self.sendEncapsulatedReply(senderTag, json.dumps({"nonce": nonce}), action="challenge", context="login")
        logger.info("handleLogin - sending challenge")

    async def handleLoginResponse(self, messageData, senderTag):
        """
        Handle the login response from the client.
        """
        signature = messageData.get("signature")
        user_details = self.NONCES.get(senderTag)

        if not user_details:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: no pending login for sender",
                action="challengeResponse",
                context="login"
            )
            logger.warning("handleLoginResponse - no pending login for sender :(")
            return

        username, publicKey, nonce = user_details

        # Verify the signature
        if self.cryptoUtils.verify_signature(publicKey, nonce, signature):
            # Look up the user in the database
            userRecord = self.databaseManager.getUserByUsername(username)
            if userRecord:
                dbSenderTag = userRecord[2]  # Stored senderTag

                # If the senderTag has changed, update it in the database
                if dbSenderTag != senderTag:
                    self.databaseManager.updateUserField(username, "senderTag", senderTag)

            # Set user as online in Redis if available
            if self.redis_manager and self.redis_manager.connection_status == "connected":
                await self.redis_manager.set_presence(username, "online", expiry=300)
                
                # Notify other users that this user is online
                notification = {
                    "type": "presence_update",
                    "username": username,
                    "status": "online",
                    "timestamp": time.time()
                }
                await self.redis_manager.publish("presence_updates", notification)
                logger.info(f"Published presence update for {username}: online")

            await self.sendEncapsulatedReply(
                senderTag,
                "success",
                action="challengeResponse",
                context="login"
            )
            del self.NONCES[senderTag]  # Clean up after successful login
            logger.info("handleLoginResponse - success!")
        else:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: invalid signature",
                action="challengeResponse",
                context="login"
            )
            del self.NONCES[senderTag]
            logger.warning("handleLoginResponse - invalid signature :(")

    async def handlePresenceUpdate(self, messageData, senderTag):
        """
        Handle presence update requests from clients.
        """
        if not self.redis_manager or self.redis_manager.connection_status != "connected":
            await self.sendEncapsulatedReply(
                senderTag,
                "error: presence service unavailable",
                action="presenceResponse",
                context="presence"
            )
            return

        username = messageData.get("username")
        status = messageData.get("status", "online")
        signature = messageData.get("signature")

        # Verify the request is legitimate
        user = self.databaseManager.getUserByUsername(username)
        if not user:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: user not found",
                action="presenceResponse",
                context="presence"
            )
            return

        dbSenderTag = user[2]
        dbPublicKey = user[1]

        # Simple validation - sender tag must match or signature must be valid
        data_to_verify = json.dumps({"username": username, "status": status})
        is_valid = (dbSenderTag == senderTag) or self.cryptoUtils.verify_signature(dbPublicKey, data_to_verify, signature)

        if not is_valid:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: unauthorized presence update",
                action="presenceResponse",
                context="presence"
            )
            return
            
        # Update presence
        if status == "offline":
            await self.redis_manager.set_presence(username, "offline")
        else:
            await self.redis_manager.set_presence(username, "online")
            
        # Broadcast presence update
        notification = {
            "type": "presence_update",
            "username": username,
            "status": status,
            "timestamp": time.time()
        }
        await self.redis_manager.publish("presence_updates", notification)
        
        # Return success
        await self.sendEncapsulatedReply(
            senderTag,
            "success",
            action="presenceResponse",
            context="presence"
        )
        logger.info(f"Updated presence for {username}: {status}")

    async def sendEncapsulatedReply(self, recipientTag, content, action="challengeResponse", context=None):
        """
        Send an encapsulated reply message.
        :param recipientTag: The recipient's sender tag.
        :param content: The content to send back.
        :param action: The action type of the reply (default is "challengeResponse").
        :param context: Additional context for the reply (e.g., 'registration').
        """
        # Load the server's private key
        private_key = self.cryptoUtils.load_private_key(os.getenv("NYM_CLIENT_ID"))
        if private_key is None:
            logger.error("sendEncapsulatedReply - server priv key not found :(")
            return
        
        signature = self.cryptoUtils.sign_message(os.getenv("NYM_CLIENT_ID"), content)
        if signature is None:
            logger.error("sendEncapsulatedReply - failed to sign message :(")
            return

        replyMessage = {
            "type": "reply",
            "message": json.dumps({
                "action": action,
                "content": content,
                "context": context,
                "signature": signature
            }),
            "senderTag": recipientTag
        }
        await self.websocketManager.send(replyMessage)
