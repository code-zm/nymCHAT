import json
import secrets
import os
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature, decode_dss_signature
from cryptographyUtils import CryptoUtils

class MessageUtils:
    NONCES = {}  # Temporary storage for nonces
    PENDING_USERS = {}  # Temporary storage for user details during registration

    def __init__(self, websocketManager, databaseManager, crypto_utils):
        self.websocketManager = websocketManager
        self.databaseManager = databaseManager
        self.cryptoUtils = CryptoUtils()

        # Ensure the server's key pair exists
        if not os.path.exists("keys/nymserver_private_key.pem"):
            print("[INFO] Generating server key pair...")
            self.cryptoUtils.generate_key_pair("nymserver")
            print("[INFO] Server key pair generated.")

    def verify_signature(self, publicKeyPem, signature, message):
        try:
            publicKey = load_pem_private_key(publicKeyPem.encode(), None)
            publicKey.verify(
                signature, message.encode(), ec.ECDSA(hashes.SHA256())
            )
            return True
        except Exception as e:
            print(f"Error verifying signature: {e}")
            return False

    async def processMessage(self, messageData):
        messageType = messageData.get("type")

        if messageType == "received":
            await self.processReceivedMessage(messageData)
        else:
            print(f"Unknown message type: {messageType}")

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
                print(f"Unknown encapsulated action: {action}")
        except json.JSONDecodeError:
            print("Error decoding encapsulated message")


    async def handleSend(self, messageData, senderTag):
        """
        Handle a direct 'send' message request from a client.
        The incoming messageData should look like:
            {
              "action": "send",
              "content": "<JSON string with 'sender', 'recipient', 'body'>",
              "signature": "<hex_signature>"
            }
        Example:
            {
              "action": "send",
              "content": "{\"sender\": \"prod\", \"recipient\": \"Nym2025\", \"body\": \"hello\"}",
              "signature": "304402202d111c52f..."
            }

        Steps:
        1. Parse the raw 'content' string to get 'sender', 'recipient', 'body'.
        2. Look up the sender by username in the DB.
        3. Check that the sender in the DB has the same senderTag as the inbound message.
        4. Verify the signature using the sender's public key.
        5. Look up the recipient in the DB, get their senderTag.
        6. Forward the message to the recipient, then confirm to the sender.
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

        # Parse the inner JSON for actual message details
        # e.g. {"sender":"prod","recipient":"Nym2025","body":"hello"}
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

        # Extract the sender username and recipient username
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

        # Look up the sender by username
        senderRecord = self.databaseManager.getUserByUsername(sender_username)
        if not senderRecord:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: unrecognized sender username",
                action="sendResponse",
                context="chat"
            )
            return

        # senderRecord typically is (username, publicKey, dbSenderTag, ...)
        dbSenderTag = senderRecord[2]
        dbPublicKey = senderRecord[1]

        # Verify the inbound senderTag matches the DB’s senderTag for this user
        if dbSenderTag != senderTag:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: senderTag mismatch",
                action="sendResponse",
                context="chat"
            )
            return

        # Now verify the signature (over the raw content_str) with the sender's public key
        if not self.cryptoUtils.verify_signature(dbPublicKey, content_str, signature):
            await self.sendEncapsulatedReply(
                senderTag,
                "error: invalid signature",
                action="sendResponse",
                context="chat"
            )
            return

        # Look up the target/recipient user by username
        targetUser = self.databaseManager.getUserByUsername(recipient_username)
        if not targetUser:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: recipient not found",
                action="sendResponse",
                context="chat"
            )
            return

        # The recipient's senderTag is usually at index 2
        targetSenderTag = targetUser[2]

        # Build the payload that we'll forward to the recipient
        forwardPayload = {
            "sender": sender_username,
            # Forward the original content string if the recipient needs 
            # to verify the signature or parse the 'body' themselves.
            "body": json.loads(content_str)["body"],
        }

        # Send it to the recipient (using their senderTag)
        await self.sendEncapsulatedReply(
            targetSenderTag,
            json.dumps(forwardPayload),
            action="incomingMessage",
            context="chat"
        )

        # Optionally confirm to the sender that we forwarded the message
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
            await self.sendEncapsulatedReply(senderTag, "error: no pending login for sender", action="challengeResponse", context="login")
            return

        username, publicKey, nonce = user_details

        # Verify the signature
        if self.cryptoUtils.verify_signature(publicKey, nonce, signature):
            await self.sendEncapsulatedReply(senderTag, "success", action="challengeResponse", context="login")
            del self.NONCES[senderTag]  # Clean up after successful login
        else:
            await self.sendEncapsulatedReply(senderTag, "error: invalid signature", action="challengeResponse", context="login")
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
            print("[ERROR] Server private key not found.")
            return
        
        if isinstance(content, str):  # If content is already a JSON string
            payload = content
        else:
            payload = json.dumps(content)  # Serialize the content

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
