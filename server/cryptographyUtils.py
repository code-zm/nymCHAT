import os
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature, decode_dss_signature
from logConfig import logger

class CryptoUtils:
    def __init__(self, key_dir="keys"):
        """Initialize the CryptoUtils with a directory for storing keys."""
        self.key_dir = key_dir
        self.private_key = None  # Will store the loaded private key in memory
        if not os.path.exists(key_dir):
            os.makedirs(key_dir)
            logger.info(f"Created key directory at {key_dir}")

    def generate_key_pair(self, username):
        """Generate a private/public key pair and save it to files."""
        try:
            private_key = ec.generate_private_key(ec.SECP256R1())
            public_key = private_key.public_key()

            private_key_path = os.path.join(self.key_dir, f"{username}_private_key.pem")
            public_key_path = os.path.join(self.key_dir, f"{username}_public_key.pem")
            
            # Save private key
            with open(private_key_path, "wb") as f:
                f.write(
                    private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                )

            # Save public key
            with open(public_key_path, "wb") as f:
                f.write(
                    public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                )

            logger.info(f"Generated key pair for {username}")
            return private_key, public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode()
        except Exception as e:
            logger.error(f"Error generating key pair for {username}: {e}")
            return None, None

    def load_private_key(self, username):
        """Load the private key from file."""
        if self.private_key:
            return self.private_key  # Return the cached private key

        try:
            private_key_path = os.path.join(self.key_dir, f"{username}_private_key.pem")
            with open(private_key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(f.read(), password=None)
            logger.info(f"Loaded private key for {username}")
            return self.private_key
        except Exception as e:
            logger.error(f"Error loading private key for {username}: {e}")
            return None

    def load_public_key(self, username):
        """Load the public key from file."""
        try:
            public_key_path = os.path.join(self.key_dir, f"{username}_public_key.pem")
            with open(public_key_path, "rb") as f:
                public_key = serialization.load_pem_public_key(f.read())
            logger.info(f"Loaded public key for {username}")
            return public_key
        except Exception as e:
            logger.error(f"Error loading public key for {username}: {e}")
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
            logger.info(f"Message signed by {username}")
            private_key = None
            logger.info("Cleared Private Key from Memory")
            return encode_dss_signature(r, s).hex()
        except Exception as e:
            logger.error(f"Error signing message for {username}: {e}")
            private_key = None
            logger.info("Cleared Private Key from Memory")
            return None

    def verify_signature(self, publicKeyPem, message, signature):
        """
        Verify a message signature using the provided public key in PEM format.
        :param publicKeyPem: The public key in PEM format.
        :param message: The original message that was signed.
        :param signature: The signature to verify (in hexadecimal format).
        :return: True if the signature is valid, False otherwise.
        """
        try:
            public_key = serialization.load_pem_public_key(publicKeyPem.encode())
            r, s = decode_dss_signature(bytes.fromhex(signature))
            public_key.verify(
                encode_dss_signature(r, s),
                message.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            logger.info("Signature verification successful")
            return True
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False


