# messageHandler.py
import json
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature

class MessageUtils:
    def __init__(self, websocketManager, databaseManager):
        self.websocketManager = websocketManager
        self.databaseManager = databaseManager

    def verifySignature(self, publicKeyPem, signature, message):
        try:
            publicKey = load_pem_public_key(publicKeyPem.encode())
            publicKey.verify(signature, message.encode(), ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            return False
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
            else:
                print(f"Unknown encapsulated action: {action}")
        except json.JSONDecodeError:
            print("Error decoding encapsulated message")

    async def handleRegister(self, messageData, senderTag):
        username = messageData.get("username")
        publicKey = messageData.get("publicKey")

        if not username or not publicKey:
            await self.sendConfirmation(senderTag, "error: missing username or public key")
            return

        if self.databaseManager.getUserByUsername(username):
            await self.sendConfirmation(senderTag, "error: username already in use")
            return

        if self.databaseManager.getUserBySenderTag(senderTag):
            await self.sendConfirmation(senderTag, "error: senderTag already in use")
            return

        if self.databaseManager.addUser(username, publicKey, senderTag):
            print(f"User {username} successfully registered with senderTag {senderTag}.")
            await self.sendConfirmation(senderTag, "success")
        else:
            await self.sendConfirmation(senderTag, "error: registration failed")

    async def handleQuery(self, messageData, senderTag):
        username = messageData.get("target")
        user = self.databaseManager.getUserByUsername(username)

        if user:
            await self.sendConfirmation(user[2], "confirm")  # User's senderTag is in the 3rd column
        else:
            await self.sendConfirmation(senderTag, "deny")

    async def handleSend(self, messageData, senderTag):
        recipient = messageData.get("target")
        content = messageData.get("content")
        user = self.databaseManager.getUserByUsername(recipient)

        if user:
            message = {
                "type": "reply",
                "message": content,
                "senderTag": user[2],  # User's senderTag is in the 3rd column
            }
            await self.websocketManager.send(message)

    async def handleSendGroup(self, messageData, senderTag):
        groupId = messageData.get("target")
        content = messageData.get("content")
        group = self.databaseManager.getGroup(groupId)

        if group:
            userList = json.loads(group[1])  # User list is in the 2nd column
            for username in userList:
                user = self.databaseManager.getUserByUsername(username)
                if user:
                    message = {
                        "type": "message",
                        "recipient": user[2],
                        "message": content,
                    }
                    await self.websocketManager.send(message)

    async def handleUpdate(self, messageData, senderTag):
        field = messageData.get("field")
        value = messageData.get("value")
        signature = messageData.get("signature")
        username = messageData.get("target")

        user = self.databaseManager.getUserByUsername(username)
        if not user:
            await self.sendConfirmation(senderTag, "deny")
            return

        publicKeyPem = user[1]  # Public key is in the 2nd column
        if not self.verifySignature(publicKeyPem, bytes.fromhex(signature), json.dumps({field: value})):
            await self.sendConfirmation(senderTag, "deny")
            return

        if self.databaseManager.updateUserField(username, field, value):
            await self.sendConfirmation(senderTag, "confirm")
        else:
            await self.sendConfirmation(senderTag, "deny")

    async def handleCreateGroup(self, messageData, senderTag):
        groupId = messageData.get("groupID")
        initialUser = [senderTag]

        if self.databaseManager.addGroup(groupId, initialUser):
            await self.sendConfirmation(senderTag, "confirm")
        else:
            await self.sendConfirmation(senderTag, "deny")

    async def handleSendInvite(self, messageData, senderTag):
        recipient = messageData.get("target")
        groupId = messageData.get("groupID")
        groupName = messageData.get("groupName")
        user = self.databaseManager.getUserByUsername(recipient)

        if user:
            inviteMessage = {
                "type": "invite",
                "recipient": user[2],
                "message": {
                    "groupID": groupId,
                    "groupName": groupName,
                },
            }
            await self.websocketManager.send(inviteMessage)

    async def sendConfirmation(self, recipientTag, status):
        confirmMessage = {
            "type": "reply",
            "message": f"{status}",
            "senderTag": recipientTag,
        }
        await self.websocketManager.send(confirmMessage)

