from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature, decode_dss_signature
import os

class CryptoUtils:
    def __init__(self, key_dir="keys"):
        """Initialize the CryptoUtils with a directory for storing keys."""
        self.key_dir = key_dir
        if not os.path.exists(key_dir):
            os.makedirs(key_dir)

    def generate_key_pair(self, username):
        """Generate a private/public key pair and save it to files."""
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()

        # Save private key
        private_key_path = os.path.join(self.key_dir, f"{username}_private_key.pem")
        with open(private_key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Save public key
        public_key_path = os.path.join(self.key_dir, f"{username}_public_key.pem")
        with open(public_key_path, "wb") as f:
            f.write(
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )

        return private_key, public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def load_private_key(self, username):
        """Load the private key from file."""
        private_key_path = os.path.join(self.key_dir, f"{username}_private_key.pem")
        with open(private_key_path, "rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
            )
        return private_key

    def load_public_key(self, username):
        """Load the public key from file."""
        public_key_path = os.path.join(self.key_dir, f"{username}_public_key.pem")
        with open(public_key_path, "rb") as f:
            public_key = serialization.load_pem_public_key(f.read())
        return public_key

    def sign_message(self, username, message):
        """Sign a message using the user's private key."""
        private_key = self.load_private_key(username)
        signature = private_key.sign(
            message.encode(),
            ec.ECDSA(hashes.SHA256())
        )
        r, s = decode_dss_signature(signature)
        return encode_dss_signature(r, s).hex()

    def verify_signature(self, publicKeyPem, message, signature):
        """
        Verify a message signature using the provided public key in PEM format.
        :param publicKeyPem: The public key in PEM format.
        :param message: The original message that was signed.
        :param signature: The signature to verify (in hexadecimal format).
        :return: True if the signature is valid, False otherwise.
        """
        try:
            # Load the public key from the PEM string
            public_key = serialization.load_pem_public_key(publicKeyPem.encode())

            # Decode the signature from hex
            r, s = decode_dss_signature(bytes.fromhex(signature))

            # Verify the signature
            public_key.verify(
                encode_dss_signature(r, s),
                message.encode(),
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except Exception as e:
            print(f"Error verifying signature: {e}")
            return False
