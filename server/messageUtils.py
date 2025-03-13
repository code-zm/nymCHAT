import json
import secrets
import os
import re
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

    def __init__(self, websocketManager, databaseManager, crypto_utils):
        SERVER_USERNAME = os.getenv("SERVER_USERNAME", "nymserver")
        SERVER_KEY_PATH = os.path.join(os.getenv("KEYS_DIR", "storage/keys"), f"{SERVER_USERNAME}_keys")

        self.websocketManager = websocketManager
        self.databaseManager = databaseManager
        self.cryptoUtils = CryptoUtils(SERVER_KEY_PATH)
        # Ensure the server's key pair exists
        if not os.path.exists(SERVER_KEY_PATH):
            logger.info("Generating server key pair...")
            self.cryptoUtils.generate_key_pair(SERVER_USERNAME)
            logger.info("Server key pair generated.")
    
    @staticmethod
    def is_valid_username(username):
        """Validates that the username contains only letters, numbers, '-', or '_'"""
        return bool(re.fullmatch(r"[A-Za-z0-9_-]+", username))


    def verify_signature(self, publicKeyPem, signature, message):
        try:
            publicKey = load_pem_private_key(publicKeyPem.encode(), None)
            publicKey.verify(
                signature, message.encode(), ec.ECDSA(hashes.SHA256())
            )
            return True
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False

    async def processMessage(self, messageData):
        messageType = messageData.get("type")

        if messageType == "received":
            await self.processReceivedMessage(messageData)
        else:
            logger.error(f"Unknown message type: {messageType}")

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
            else:
                logger.error(f"Unknown encapsulated action: {action}")
        except json.JSONDecodeError:
            logger.error("Error decoding encapsulated message")


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

        # Confirm success to the sender.
        await self.sendEncapsulatedReply(
            senderTag,
            "success",
            action="sendResponse",
            context="chat"
        )


    
    async def handleQuery(self, messageData, senderTag):
        """
        Handle a user discovery query:
          - The client sends a 'username' field to look up.
          - We return either the user details (username and publicKey) 
            or "No user found".
        Example incoming data:
        {
          "action": "query",
          "username": "<some_username>"
        }
        """
        target_username = messageData.get("username")
        if not target_username:
            # If 'username' is missing, let the client know
            await self.sendEncapsulatedReply(
                senderTag,
                "error: missing 'username' field",
                action="queryResponse",
                context="query"
            )
            return

        # Look up the user record in the DB
        user = self.databaseManager.getUserByUsername(target_username)
        if user:
            # Depending on your schema, user might be (username, publicKey, senderTag, ...)
            # We'll just extract the first two.
            username, publicKey = user[0], user[1]

            # Only return the username and publicKey
            user_data = {
                "username": username,
                "publicKey": publicKey
            }

            await self.sendEncapsulatedReply(
                senderTag,
                json.dumps(user_data),
                action="queryResponse",
                context="query"
            )
        else:
            # No user found
            await self.sendEncapsulatedReply(
                senderTag,
                "No user found",
                action="queryResponse",
                context="query"
            )



    async def handleRegister(self, messageData, senderTag):
        username = messageData.get("usernym")
        publicKey = messageData.get("publicKey")

        if not username or not publicKey:
            await self.sendEncapsulatedReply(senderTag, "error: missing username or public key", action="challengeResponse", context="registration")
            return

        if not MessageUtils.is_valid_username(username):
            await self.sendEncapsulatedReply(senderTag, "error: invalid username format", action="challengeResponse", context="registration")
            return

        if self.databaseManager.getUserByUsername(username):
            await self.sendEncapsulatedReply(senderTag, "error: username already in use", action="challengeResponse", context="registration")
            return

        # Generate a nonce and store it in PENDING_USERS
        nonce = secrets.token_hex(16)
        self.PENDING_USERS[senderTag] = (username, publicKey, nonce)

        # Send the challenge to the client
        await self.sendEncapsulatedReply(senderTag, json.dumps({"nonce": nonce}), action="challenge", context="registration")

    async def handleRegistrationResponse(self, messageData, senderTag):
        signature = messageData.get("signature")
        user_details = self.PENDING_USERS.get(senderTag)

        if not user_details:
            await self.sendEncapsulatedReply(senderTag, "error: no pending registration for sender", action="challengeResponse", context="registration")
            return

        username, publicKey, nonce = user_details

        # Verify the signature
        if self.cryptoUtils.verify_signature(publicKey, nonce, signature):
            if self.databaseManager.addUser(username, publicKey, senderTag):
                await self.sendEncapsulatedReply(senderTag, "success", action="challengeResponse", context="registration")
                del self.PENDING_USERS[senderTag]  # Clean up after successful registration
            else:
                await self.sendEncapsulatedReply(senderTag, "error: database failure", action="challengeResponse", context="registration")
        else:
            await self.sendEncapsulatedReply(senderTag, "error: signature verification failed", action="challengeResponse", context="registration")
            del self.PENDING_USERS[senderTag]  # Clean up after failed verification

    async def handleLogin(self, messageData, senderTag):
        """
        Handle the login request from the client.
        """
        username = messageData.get("usernym")

        if not username:
            await self.sendEncapsulatedReply(senderTag, "error: missing username", action="challengeResponse", context="login")
            return

        user = self.databaseManager.getUserByUsername(username)
        if not user:
            await self.sendEncapsulatedReply(senderTag, "error: user not found", action="challengeResponse", context="login")
            return

        # Generate a nonce and store it
        nonce = secrets.token_hex(16)
        self.NONCES[senderTag] = (username, user[1], nonce)  # user[1] is the public key

        # Send the challenge to the client
        await self.sendEncapsulatedReply(senderTag, json.dumps({"nonce": nonce}), action="challenge", context="login")


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

            await self.sendEncapsulatedReply(
                senderTag,
                "success",
                action="challengeResponse",
                context="login"
            )
            del self.NONCES[senderTag]  # Clean up after successful login
        else:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: invalid signature",
                action="challengeResponse",
                context="login"
            )
            del self.NONCES[senderTag]




    async def sendEncapsulatedReply(self, recipientTag, content, action="challengeResponse", context=None):
        """
        Send an encapsulated reply message.
        :param recipientTag: The recipient's sender tag.
        :param content: The content to send back.
        :param action: The action type of the reply (default is "challengeResponse").
        :param context: Additional context for the reply (e.g., 'registration').
        """
        # Load the server's private key
        private_key = self.cryptoUtils.load_private_key("nymserver")
        if private_key is None:
            logger.error("Server private key not found.")
            return
        
        signature = private_key.sign(
            content.encode(),
            ec.ECDSA(hashes.SHA256())
        )

        replyMessage = {
            "type": "reply",
            "message": json.dumps({
                "action": action,
                "content": content,
                "context": context,
                "signature": signature.hex()
            }),
            "senderTag": recipientTag
        }
        await self.websocketManager.send(replyMessage)

