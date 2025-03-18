import os
import base64
import secrets
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature, decode_dss_signature
from logConfig import logger
from envLoader import load_env

load_env()

class CryptoUtils:
    def __init__(self, key_dir, password):
        """Initialize the CryptoUtils with a directory for storing keys and a password for encryption."""
        self.key_dir = os.getenv("KEYS_DIR", "storage/keys")
        self.password = password  # Store password in memory
        if not os.path.exists(self.key_dir):
            os.makedirs(self.key_dir)

    def _derive_key(self, salt):
        """Derive a 256-bit AES key using PBKDF2 with 100,000 iterations."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend(),
        )
        return kdf.derive(self.password.encode())

    def _encrypt_private_key(self, private_key_pem):
        """Encrypt the private key using AES-256-GCM."""
        salt = secrets.token_bytes(16)
        key = self._derive_key(salt)
        iv = secrets.token_bytes(12)
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(private_key_pem) + encryptor.finalize()

        return base64.b64encode(salt + iv + encryptor.tag + ciphertext).decode()

    def _decrypt_private_key(self, encrypted_data):
        """Decrypt the AES-256-GCM encrypted private key."""
        encrypted_data = base64.b64decode(encrypted_data)
        salt, iv, tag, ciphertext = encrypted_data[:16], encrypted_data[16:28], encrypted_data[28:44], encrypted_data[44:]
        key = self._derive_key(salt)
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()

    def generate_key_pair(self, username):
        """Generate and securely save a private/public key pair."""
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        encrypted_private_key = self._encrypt_private_key(private_key_pem)

        private_key_path = os.path.join(self.key_dir, f"{username}_private_key.enc")
        public_key_path = os.path.join(self.key_dir, f"{username}_public_key.pem")

        with open(private_key_path, "w") as f:
            f.write(encrypted_private_key)

        with open(public_key_path, "wb") as f:
            f.write(
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )

        logger.info(f"generateKeyPair - success!")
        return private_key, public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def load_private_key(self, username):
        """Load and decrypt the private key from storage."""
        private_key_path = os.path.join(self.key_dir, f"{username}_private_key.enc")

        if not os.path.exists(private_key_path):
            return None

        with open(private_key_path, "r") as f:
            encrypted_data = f.read()

        try:
            decrypted_pem = self._decrypt_private_key(encrypted_data)
            private_key = serialization.load_pem_private_key(decrypted_pem, password=None, backend=default_backend())
            return private_key
        except Exception as e:
            logger.error(f"loadPrivateKey - error :( |{e}")
            return None

    def load_public_key(self, username):
        """Load the public key from file."""
        try:
            public_key_path = os.path.join(self.key_dir, f"{username}_public_key.pem")
            with open(public_key_path, "rb") as f:
                public_key = serialization.load_pem_public_key(f.read())
            return public_key
        except Exception as e:
            logger.error(f"loadPublicKey - error :( | {e}")
            return None

    def sign_message(self, username, message):
        """Sign a message using the user's private key."""
        private_key = self.load_private_key(username)
        if not private_key:
            return None

        try:
            signature = private_key.sign(
                message.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            r, s = decode_dss_signature(signature)
            logger.info(f"signMessage - success!")
            return encode_dss_signature(r, s).hex()
        except Exception as e:
            logger.error(f"signMessage - error :( | {e}")
            return None

    def verify_signature(self, publicKeyPem, message, signature):
        """Verify a message signature using the provided public key in PEM format."""
        try:
            public_key = serialization.load_pem_public_key(publicKeyPem.encode())
            r, s = decode_dss_signature(bytes.fromhex(signature))
            public_key.verify(
                encode_dss_signature(r, s),
                message.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            logger.info("verifySignature - success!")
            return True
        except Exception as e:
            logger.error(f"verifySignature - error :( | {e}")
            return False
