from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature, decode_dss_signature
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import os
import json

class CryptoUtils:
    def __init__(self, storage_dir="storage"):
        """Initialize the CryptoUtils with a base storage directory."""
        self.storage_dir = storage_dir
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)

    # ----------------------------------------------
    # 🔑 KEY MANAGEMENT
    # ----------------------------------------------
    def generate_key_pair(self, username):
        """Generate a private/public key pair."""
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        return private_key, public_key_pem

    def save_keys(self, username, private_key, public_key_pem):
        """Save the private and public keys to files."""
        user_dir = os.path.join(self.storage_dir, username)
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)

        # Save private key
        private_key_path = os.path.join(user_dir, f"{username}_private_key.pem")
        with open(private_key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Save public key
        public_key_path = os.path.join(user_dir, f"{username}_public_key.pem")
        with open(public_key_path, "wb") as f:
            f.write(public_key_pem.encode())

    def load_private_key(self, username):
        """Load the private key from the user's folder."""
        private_key_path = os.path.join(self.storage_dir, username, f"{username}_private_key.pem")
        with open(private_key_path, "rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
            )
        return private_key

    def load_public_key(self, username):
        """Load the public key from the user's folder."""
        public_key_path = os.path.join(self.storage_dir, username, f"{username}_public_key.pem")
        with open(public_key_path, "rb") as f:
            public_key = serialization.load_pem_public_key(f.read())
        return public_key

    # ----------------------------------------------
    # 🔒 SIGNING & VERIFICATION
    # ----------------------------------------------
    def sign_message(self, private_key, message):
        """Sign a message using ECDSA."""
        if not isinstance(message, str):
            raise ValueError("sign_message expects a raw string, not a dictionary.")

        signature = private_key.sign(
            message.encode(),
            ec.ECDSA(hashes.SHA256())
        )
        return signature.hex()

    def verify_signature(self, public_key, message, signature):
        """Verify the authenticity of a signed message."""
        try:
            r, s = decode_dss_signature(bytes.fromhex(signature))
            public_key.verify(
                encode_dss_signature(r, s),
                message.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except Exception:
            return False

    # ----------------------------------------------
    # 🔑 ENCRYPTION & DECRYPTION WITH ECDH
    # ----------------------------------------------
    def encrypt_message(self, recipient_public_key_pem, message):
        """Encrypts a message using ECDH key exchange + AES-GCM."""

        # ✅ Automatically convert a string public key to a PEM-encoded object
        if isinstance(recipient_public_key_pem, str):
            try:
                recipient_public_key = serialization.load_pem_public_key(recipient_public_key_pem.encode())
            except ValueError:
                raise ValueError("❌ Invalid PEM format for recipient public key.")
        else:
            recipient_public_key = recipient_public_key_pem  # Assume it's already a key object

        # ✅ Generate an ephemeral key pair
        ephemeral_private_key = ec.generate_private_key(ec.SECP256R1())
        ephemeral_public_key = ephemeral_private_key.public_key()

        # ✅ Compute shared secret using ephemeral private key and recipient's public key
        shared_secret = ephemeral_private_key.exchange(ec.ECDH(), recipient_public_key)
        salt = os.urandom(16) # 128 bits of salt
        # ✅ Derive AES key using HKDF
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b'ECDH session key'
        ).derive(shared_secret)

        # ✅ Encrypt message using AES-GCM
        encrypted_payload = self._aes_encrypt(message, derived_key)

        # ✅ Serialize ephemeral public key
        ephemeral_public_key_pem = ephemeral_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

        return {
            "ephemeralPublicKey": ephemeral_public_key_pem,
            "salt": salt.hex(),
            "encryptedBody": encrypted_payload
        }

    def decrypt_message(self, recipient_private_key, encrypted_message):
        """Decrypt an encrypted message using ECDH key exchange and AES-GCM."""

        try:
            # ✅ Extract ephemeral public key and encrypted body
            ephemeral_public_key_pem = encrypted_message["ephemeralPublicKey"]
            encrypted_body = encrypted_message["encryptedBody"]
            salt = bytes.fromhex(encrypted_message["salt"])

            ephemeral_public_key = serialization.load_pem_public_key(ephemeral_public_key_pem.encode())

            # ✅ Compute shared secret using recipient’s private key & sender’s ephemeral public key
            shared_key = recipient_private_key.exchange(ec.ECDH(), ephemeral_public_key)

            # ✅ Derive AES key using HKDF
            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                info=b'ECDH session key'
            ).derive(shared_key)

            # ✅ Decrypt the message
            decrypted_message = self._aes_decrypt(encrypted_body, derived_key)

            return decrypted_message  # ✅ Return the plaintext message directly

        except Exception as e:
            print(f"❌ Error during decryption: {e}")
            return None


    # ----------------------------------------------
    # 🛡 AES-GCM ENCRYPTION HELPERS
    # ----------------------------------------------
    def _aes_encrypt(self, plaintext, derived_key):
        """Encrypt a message using AES-GCM."""
        iv = os.urandom(12)
        encryptor = Cipher(algorithms.AES(derived_key), modes.GCM(iv)).encryptor()
        ciphertext = encryptor.update(plaintext.encode()) + encryptor.finalize()
        return {
            "iv": iv.hex(),
            "ciphertext": ciphertext.hex(),
            "tag": encryptor.tag.hex()
        }

    def _aes_decrypt(self, enc_dict, derived_key):
        """Decrypt an encrypted message using AES-GCM."""
        iv = bytes.fromhex(enc_dict["iv"])
        ciphertext = bytes.fromhex(enc_dict["ciphertext"])
        tag = bytes.fromhex(enc_dict["tag"])
        decryptor = Cipher(algorithms.AES(derived_key), modes.GCM(iv, tag)).decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        return plaintext.decode()
