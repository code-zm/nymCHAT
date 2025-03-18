import json
import asyncio
from nicegui import ui
from datetime import datetime
from cryptography.hazmat.primitives import serialization
from mixnetMessages import MixnetMessage
from cryptographyUtils import CryptoUtils
from connectionUtils import MixnetConnectionClient
from dbUtils import SQLiteManager
from logUtils import logger

class MessageHandler:
    def __init__(self, crypto_utils: CryptoUtils, connection_client: MixnetConnectionClient):
        self.crypto_utils = crypto_utils
        self.connection_client = connection_client
        self.current_user = {"username": None}
        self.temporary_keys = {"private_key": None, "public_key": None}
        self.db_manager = None  # Will be set after login/registration

        # Wait-for-completion events
        self.registration_complete = asyncio.Event()
        self.login_complete = asyncio.Event()
        
        # Registration / login status (success or failure)
        self.registration_successful = None
        self.login_successful = None

        # Query flow
        self.query_result_event = asyncio.Event()
        self.query_result = None

        # [OPTIONAL] references to UI or chat state
        self.chat_messages = None
        self.chat_list = None
        self.active_chat = None
        self.render_chat_fn = None
        self.chat_list_sidebar_fn = None  # For refreshing the chat list sidebar
        self.chat_container = None
        self.new_message_callback = None  # To notify UI of new messages

        # Ephemeral mapping of usernames to nym addresses for p2p routing
        self.nym_addresses = {}  # {username: nym_address}

        # Store our own nym address (to be set externally after mixnet initialization)
        self.nym_address = None

    def update_nym_address(self, nym_address):
        """Update the client's own nym address in MessageHandler."""
        self.nym_address = nym_address
        logger.info(f"Updated own nym address in MessageHandler: {nym_address}")

    def set_ui_state(self, messages, chat_list, get_active_chat, render_chat, chat_container, chat_list_sidebar_fn=None):
        """
        Optionally call this from runClient.py if you want to update UI state
        directly from handle_incoming_message.
        'get_active_chat' can be a function or a reference to the global variable.
        """
        self.chat_messages = messages
        self.chat_list = chat_list
        self._get_active_chat = get_active_chat
        self.render_chat_fn = render_chat
        self.chat_container = chat_container
        self.chat_list_sidebar_fn = chat_list_sidebar_fn  # Store reference for sidebar refresh

    # --------------------------------------------------------------------------
    # Registration & Login
    # --------------------------------------------------------------------------

    async def register_user(self, username, first_name="", last_name=""):
        try:
            self.current_user["username"] = username
            self.registration_complete.clear()

            private_key, public_key = self.crypto_utils.generate_key_pair(username)
            self.temporary_keys["private_key"] = private_key
            self.temporary_keys["public_key"] = public_key
            logger.info(f"Keypair generated for user: {username}")

            # Send a 'register' message (only username and public key are used)
            register_msg = MixnetMessage.register(usernym=username, publicKey=public_key)
            await self.connection_client.send_message(register_msg)
            logger.info("Registration message sent; waiting for challenge...")

            await self.registration_complete.wait()

        except Exception as e:
            logger.error(f"Registration error: {e}")

    async def login_user(self, username):
        try:
            self.current_user["username"] = username
            self.login_complete.clear()

            private_key = self.crypto_utils.load_private_key(username)
            if not private_key:
                logger.error(f"No private key for {username}")
                return

            self.temporary_keys["private_key"] = private_key
            logger.info(f"Loaded private key for {username}")

            msg = MixnetMessage.login(username)
            await self.connection_client.send_message(msg)
            logger.info("Login message sent; waiting for challenge...")

            await self.login_complete.wait()

        except Exception as e:
            logger.error(f"Login error: {e}")

    async def handle_registration_challenge(self, content):
        nonce = content.get("nonce")
        if not nonce:
            logger.error("No nonce in registration challenge.")
            return
        private_key = self.temporary_keys.get("private_key")
        if not private_key:
            logger.error("No private key for registration.")
            return

        try:
            signature = self.crypto_utils.sign_message(private_key, nonce)
            resp = MixnetMessage.registrationResponse(self.current_user["username"], signature)
            await self.connection_client.send_message(resp)
            logger.info("Registration challenge response sent.")
        except Exception as e:
            logger.error(f"Signing registration nonce: {e}")

    async def handle_login_challenge(self, content):
        nonce = content.get("nonce")
        if not nonce:
            logger.error("No nonce in login challenge.")
            return
        private_key = self.temporary_keys.get("private_key")
        if not private_key:
            logger.error("No private key for login.")
            return

        try:
            signature = self.crypto_utils.sign_message(private_key, nonce)
            resp = MixnetMessage.loginResponse(self.current_user["username"], signature)
            await self.connection_client.send_message(resp)
            logger.info("Login challenge response sent.")
        except Exception as e:
            logger.error(f"Signing login nonce: {e}")

    async def handle_registration_response(self, content):
        """
        Handles the response after the registration challenge has been completed.
        """
        if content == "success":
            logger.info("Registration successful!")
            username = self.current_user["username"]
            priv_k = self.temporary_keys["private_key"]
            pub_k = self.temporary_keys["public_key"]

            try:
                self.crypto_utils.save_keys(username, priv_k, pub_k)
                logger.info("Keys saved.")
            except Exception as e:
                logger.error(f"Saving keys: {e}")
                self.registration_successful = False
                self.registration_complete.set()  # Ensure the event is set
                return

            try:
                self.db_manager = SQLiteManager(username)
                logger.info("DB initialized for user: %s", username)
            except Exception as e:
                logger.error(f"DB init: {e}")
                self.registration_successful = False
                self.registration_complete.set()  # Ensure the event is set
                return

            self.registration_successful = True  # Registration is successful
            self.registration_complete.set()  # Signal that registration is complete

        else:
            logger.error(f"Registration failed: {content}")
            self.registration_successful = False
            self.registration_complete.set()

    async def handle_login_response(self, content):
        """
        Handles the response after the login challenge has been completed.
        """
        if content == "success":
            logger.info("Login successful!")
            username = self.current_user["username"]
            try:
                self.db_manager = SQLiteManager(username)
                logger.info("DB manager created.")
                self.db_manager.create_user_tables(username)
            except Exception as e:
                logger.error(f"DB init: {e}")
                self.login_successful = False
                self.login_complete.set()
                return

            self.login_successful = True
            self.login_complete.set()

        else:
            logger.error(f"Login failed: {content}")
            self.login_successful = False
            self.login_complete.set()

    # --------------------------------------------------------------------------
    # Sending Direct Messages (All messages encrypted)
    # --------------------------------------------------------------------------
    async def send_direct_message(self, recipient_username, message_content):
        if not recipient_username or not message_content.strip():
            return

        sender_private_key = self.crypto_utils.load_private_key(self.current_user["username"])
        if not sender_private_key:
            logger.error("No private key to send message.")
            return

        if not self.db_manager:
            logger.error("DB manager not initialized.")
            return

        contact = self.db_manager.get_contact(self.current_user["username"], recipient_username)
        if not contact:
            logger.error(f"No contact record found for {recipient_username}. Cannot send message.")
            return

        existing_msgs = self.db_manager.get_messages_by_contact(self.current_user["username"], recipient_username)
        initial_message = not existing_msgs

        recipient_public_key_pem = contact[1]

        # Maintain original message format
        wrapped_message = json.dumps({"type": 0, "message": message_content})

        # Encrypt using ECDH + AES-GCM
        encrypted_payload = self.crypto_utils.encrypt_message(recipient_public_key_pem, wrapped_message)

        # Sign only the encryptedPayload
        encrypted_payload_str = json.dumps(encrypted_payload)  # Convert to string for signing
        payload_signature = self.crypto_utils.sign_message(sender_private_key, encrypted_payload_str)

        # Construct the body field (ENCAPSULATING SIGNATURE INSIDE `body`)
        body = {
            "encryptedPayload": encrypted_payload,  
            "payloadSignature": payload_signature  # Inner signature inside `body`
        }

        # Construct final message payload
        payload = {
            "sender": self.current_user["username"],
            "recipient": recipient_username,
            "body": body,  #  contains both encryptedPayload + signature
            "encrypted": True
        }

        # If it's an initial message, include sender's public key
        if initial_message:
            sender_public_key_obj = self.crypto_utils.load_public_key(self.current_user["username"])
            sender_public_key_pem = sender_public_key_obj.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode()
            payload["senderPublicKey"] = sender_public_key_pem

        # Sign the full message (for the server)
        payload_str = json.dumps(payload)
        outer_signature = self.crypto_utils.sign_message(sender_private_key, payload_str)

        # Encapsulate as per existing protocol
        if recipient_username in self.nym_addresses:
            msg = MixnetMessage.directMessage(content=payload_str, signature=outer_signature)
            msg["recipient"] = self.nym_addresses[recipient_username]
        else:
            msg = MixnetMessage.send(content=payload_str, signature=outer_signature)

        await self.connection_client.send_message(msg)
        logger.info(f"Sent direct message to {recipient_username}")

        self.db_manager.save_message(
            self.current_user["username"],
            contact_username=recipient_username,
            msg_type='to',
            message=message_content
        )


    async def send_handshake(self, recipient_username):
        """
        Sends a handshake (type 1 message) containing this client's nym address.
        """
        if self.nym_address is None:
            logger.error("Nym address not set in MessageHandler.")
            return

        sender_private_key = self.crypto_utils.load_private_key(self.current_user["username"])
        if not sender_private_key:
            logger.error("No private key available for handshake.")
            return

        if not self.db_manager:
            logger.error("DB manager not initialized.")
            return

        contact = self.db_manager.get_contact(self.current_user["username"], recipient_username)
        if not contact:
            logger.error(f"No contact record found for {recipient_username}. Cannot send handshake.")
            return

        recipient_public_key_pem = contact[1]

        # inner message format
        handshake_payload = json.dumps({"type": 1, "message": self.nym_address})

        # Encrypt and sign
        enc_result = self.crypto_utils.encrypt_message(recipient_public_key_pem, handshake_payload)
        encrypted_payload_str = json.dumps(enc_result)
        payload_signature = self.crypto_utils.sign_message(sender_private_key, encrypted_payload_str)

        payload = {
            "sender": self.current_user["username"],
            "recipient": recipient_username,
            "body": {
                "encryptedPayload": enc_result,
                "payloadSignature": payload_signature
            },
            "encrypted": True
        }

        # Sign the entire payload (for server to verify)
        payload_str = json.dumps(payload)
        signature = self.crypto_utils.sign_message(sender_private_key, payload_str)

        # If we have an ephemeral nym_address for a given user, format as directMessage & send to nym_address, else normal send to server
        if recipient_username in self.nym_addresses:
            msg = MixnetMessage.directMessage(content=payload_str, signature=signature)
            msg["recipient"] = self.nym_addresses[recipient_username]
        else:
            msg = MixnetMessage.send(content=payload_str, signature=signature)

        await self.connection_client.send_message(msg)
        logger.info(f"Sent handshake to {recipient_username}")

    async def handle_send_response(self, content):
        pass

    # --------------------------------------------------------------------------
    # Query
    # --------------------------------------------------------------------------
    async def query_user(self, target_username):
        try:
            self.query_result_event.clear()
            self.query_result = None

            msg = MixnetMessage.query(target_username)
            await self.connection_client.send_message(msg)
            logger.info(f"Sent query for user: {target_username}")

            await self.query_result_event.wait()
            return self.query_result
        except Exception as e:
            logger.error(f"query_user: {e}")
            return None

    async def handle_query_response(self, content):
        self.query_result = content
        self.query_result_event.set()
        logger.info("queryResponse received")
        if self.db_manager and isinstance(content, dict):
            username = content.get("username")
            public_key = content.get("publicKey")
            if username and public_key:
                self.db_manager.add_contact(self.current_user["username"], username, public_key)

    # --------------------------------------------------------------------------
    # Handling Incoming Messages (SINGLE CALLBACK)
    # --------------------------------------------------------------------------
    async def handle_incoming_message(self, message):
        """ Main dispatcher for handling messages """
        try:
            encapsulated_data = json.loads(message)
            action = encapsulated_data.get("action")
            context = encapsulated_data.get("context")
            content = self._parse_content(encapsulated_data.get("content"))

            handler = self.get_handler(action, context)
            if handler:
                await handler(content)
            else:
                logger.warning(f"Unknown or unhandled action '{action}', context='{context}'")
        except json.JSONDecodeError:
            logger.error("Could not decode the message content.")

    def _parse_content(self, content):
        """ Ensure content is a dictionary, converting if necessary """
        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
        return content


    def get_handler(self, action, context):
        """ Returns the appropriate handler function based on action and context """
        handlers = {
            ("challenge", "registration"): self.handle_registration_challenge,
            ("challenge", "login"): self.handle_login_challenge,
            ("challengeResponse", "registration"): self.handle_registration_response,
            ("challengeResponse", "login"): self.handle_login_response,
            ("incomingMessage", "chat"): self.handle_incoming_message_content,
            ("queryResponse", "query"): self.handle_query_response,
            ("sendResponse", "chat"): self.handle_send_response,
        }
        return handlers.get((action, context)) or handlers.get((action, None))

    async def handle_incoming_message_content(self, content):
        """Handles incoming messages, including decryption, verification, and storage."""
        logger.info("Processing incoming message")

        if not isinstance(content, dict):
            logger.error("Parsed content is not a valid dictionary after JSON decoding.")
            return

        from_user = content.get("sender")
        body = content.get("body")
        sender_pub_from_msg = content.get("senderPublicKey")  # Extract sender's long-term public key
        if not from_user or not body:
            logger.error("Malformed incoming message. Missing sender or body.")
            return

        encrypted_payload = body.get("encryptedPayload")
        payload_signature = body.get("payloadSignature")

        if not encrypted_payload or not payload_signature:
            logger.error("Malformed body. Missing encryptedPayload or payloadSignature.")
            return

        ephemeral_public_key_pem = encrypted_payload.get("ephemeralPublicKey")
        if not ephemeral_public_key_pem:
            logger.error("No ephemeral public key attached. Cannot derive shared secret.")
            return

        logger.info(f"Received message from {from_user}")

        # Retrieve sender's stored long-term public key (for signature verification)
        contact = self.db_manager.get_contact(self.current_user["username"], from_user) if self.db_manager else None
        sender_public_key_pem = contact[1] if contact else None

        # If this is the first contact, store the sender's public key
        if sender_pub_from_msg:
            if not sender_public_key_pem:  # First-time contact
                logger.info(f"Storing new sender public key for {from_user}")
                self.db_manager.add_contact(self.current_user["username"], from_user, sender_pub_from_msg)
                sender_public_key_pem = sender_pub_from_msg  #  Use this for signature verification

        # If we still don't have a long-term public key, we cannot verify the signature
        if not sender_public_key_pem:
            logger.error(f"No sender public key available for {from_user}. Cannot verify message signature.")
            return None

        sender_public_key = serialization.load_pem_public_key(sender_public_key_pem.encode())

        # Step 1: Verify the `payloadSignature` using sender's long-term key
        encrypted_payload_str = json.dumps(encrypted_payload)

        if not self.crypto_utils.verify_signature(sender_public_key, encrypted_payload_str, payload_signature):
            logger.error(f"Signature verification failed for {from_user}. Dropping message.")
            return None
        logger.info("Payload signature verified successfully!")

        # Step 2: Load recipient's private key
        recipient_private_key = self.crypto_utils.load_private_key(self.current_user["username"])
        if not recipient_private_key:
            logger.error(f"No private key available for recipient: {self.current_user['username']}.")
            return None

        # Step 3: Decrypt using the ephemeral key
        try:
            decrypted_message = self.crypto_utils.decrypt_message(
                recipient_private_key, encrypted_payload
            )

            if decrypted_message:
                logger.info(f" Decrypted message from {from_user}")
            else:
                logger.error(f"Failed to decrypt message from {from_user}.")

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None

        # Step 4: Parse JSON 
        try:
            message_obj = json.loads(decrypted_message)
        except json.JSONDecodeError:
            logger.error("Decrypted message not valid JSON")
            return None
        
        # Step 5 Check type 
        message_type = message_obj.get("type")
        actual_message = message_obj.get("message")

        if message_type == 1:
            logger.info(f"Storing handshake nym_address from {from_user}")
            self.nym_addresses[from_user] = actual_message
            return

        # Step 6 Handle normal message storage
        if from_user and actual_message and self.db_manager:
            self._store_message(from_user, actual_message)
            logger.info(f"Stored incoming message from {from_user} in DB.")

            # Update the chat UI
            self._update_chat_ui(from_user, actual_message)


    def _verify_and_decrypt_message(self, encrypted_payload, signature, from_user):
        """ Calls CryptoUtils to verify the signature and then decrypt the message """

        # Retrieve sender's stored public key
        contact = self.db_manager.get_contact(self.current_user["username"], from_user) if self.db_manager else None
        sender_public_key_pem = contact[1] if contact else None

        if not sender_public_key_pem:
            logger.error(f"No sender public key available for {from_user}. Cannot verify message.")
            return None

        sender_public_key = serialization.load_pem_public_key(sender_public_key_pem.encode())

        # Step 1: Verify Signature Before Decryption
        encrypted_payload_str = json.dumps(encrypted_payload)  # Convert dict to string for signature verification
        if not self.crypto_utils.verify_signature(sender_public_key, encrypted_payload_str, signature):
            logger.error(f"Signature verification failed for {from_user}. Dropping message.")
            return None

        # Load recipient's private key
        recipient_private_key = self.crypto_utils.load_private_key(self.current_user["username"])

        if not recipient_private_key:
            logger.error(f"No private key available for recipient {self.current_user['username']}.")
            return None

        try:
            # Step 2: Decrypt Message
            decrypted_message = self.crypto_utils.decrypt_message(
                recipient_private_key, encrypted_payload
            )

            if decrypted_message:
                logger.info(f"Successfully decrypted message from {from_user}: {decrypted_message}")
            else:
                logger.error(f"Failed to decrypt message from {from_user}.")
            
            return decrypted_message

        except Exception as e:
            logger.error(f"Decryption or verification failed: {e}")
            return None

    def _parse_message(self, decrypted_msg):
        """
        Ensures the message content is in the correct format.
        - If it's JSON, return as a dict.
        - If it's plaintext, wrap it in {"type": 0, "message": decrypted_msg}.
        """
        try:
            parsed_message = json.loads(decrypted_msg)  # Try parsing JSON
            if isinstance(parsed_message, dict):
                return parsed_message
        except json.JSONDecodeError:
            logger.error(" _parse_message: Decrypted message is not valid JSON")
            return None

    # def _handle_handshake(self, from_user, message_obj):
    #     """ Handles handshake messages and updates contact list """
    #     nym_addr = message_obj.get("message")
    #     if nym_addr:
    #         self.nym_addresses[from_user] = nym_addr
    #         logger.info(f"Received handshake from {from_user}. Updated nym address: {nym_addr}")
    #     else:
    #         logger.warning(f"Handshake message from {from_user} missing nym address.")

    def _store_message(self, from_user, actual_message):
        """ Stores message in the database """
        self.db_manager.save_message(self.current_user["username"], from_user, 'from', actual_message)
        logger.info(f"Stored incoming message from {from_user} in DB.")

    def _update_chat_ui(self, from_user, actual_message):
        """ Updates chat messages and UI elements """
        if self.chat_messages is None:
            logger.warning("chat_messages is None; UI might not be initialized.")
            return

        if from_user not in self.chat_messages:
            self.chat_messages[from_user] = []

        stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.chat_messages[from_user].append((from_user, actual_message, stamp))

        if not any(chat["id"] == from_user for chat in self.chat_list):
            self.chat_list.append({"id": from_user, "name": from_user})
            if self.chat_list_sidebar_fn:
                self.chat_list_sidebar_fn.refresh()
            logger.info(f"Added {from_user} to chat list.")

        currently_active_chat = self._get_active_chat()
        if from_user == currently_active_chat and self.render_chat_fn:
            try:
                self.render_chat_fn.refresh(self.current_user["username"], currently_active_chat, self.chat_messages)
                logger.info("Chat UI refreshed successfully.")
            except Exception as e:
                logger.error(f"Failed to refresh chat UI: {e}")
        elif self.new_message_callback:
            self.new_message_callback(from_user, actual_message)
