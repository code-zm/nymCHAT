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
        Expected messageData format:
          {
            "action": "send",
            "target": "<recipient_username>",
            "content": "<message_body>",
            "signature": "<hex_signature>"
          }
        """

        target = messageData.get("target")
        content = messageData.get("content")
        signature = messageData.get("signature")

        # Basic validation
        if not target or not content or not signature:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: missing fields (target, content, or signature)",
                action="sendResponse",
                context="chat"
            )
            return

        # Look up the sender in the DB by senderTag
        senderUser = self.databaseManager.getUserBySenderTag(senderTag)
        if not senderUser:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: unregistered sender",
                action="sendResponse",
                context="chat"
            )
            return

        # senderUser is likely a tuple: (username, publicKey, senderTag, firstName, lastName)
        # depending on how your schema is laid out
        senderUsername, senderPublicKey = senderUser[0], senderUser[1]

        # Verify the signature using the sender's public key
        if not self.cryptoUtils.verify_signature(senderPublicKey, content, signature):
            await self.sendEncapsulatedReply(
                senderTag,
                "error: invalid signature",
                action="sendResponse",
                context="chat"
            )
            return

        # Find the target user by username
        targetUser = self.databaseManager.getUserByUsername(target)
        if not targetUser:
            await self.sendEncapsulatedReply(
                senderTag,
                "error: target user not found",
                action="sendResponse",
                context="chat"
            )
            return

        targetSenderTag = targetUser[2]  # e.g. (username, publicKey, senderTag, ...)

        # Build the message we'll forward to the target user
        # They may want to see the sender's username + the original content
        forwardPayload = {
            "action": "incomingMessage",
            "from": senderUsername,
            "content": content,
            "signature": signature
        }

        # Send the forwarded message to the target user
        await self.sendEncapsulatedReply(
            targetSenderTag,
            json.dumps(forwardPayload),
            action="incomingMessage",
            context="chat"
        )

        # Optionally, inform the original sender that the message was forwarded successfully
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
          - We return either the user details or a 'No user found' message.
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
            # Suppose the schema is:
            # (username, publicKey, senderTag, firstName, lastName)
            username, publicKey, _, firstName, lastName = user
            
            user_data = {
                "username": username,
                "publicKey": publicKey,
                "firstName": firstName if firstName else "",
                "lastName": lastName if lastName else ""
            }
            
            # Send back the user info (no senderTag)
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
