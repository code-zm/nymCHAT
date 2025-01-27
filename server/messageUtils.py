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
        username = messageData.get("username")

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
