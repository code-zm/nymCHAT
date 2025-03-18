import os

def load_env(filepath=".env"):
    """Load environment variables from a .env file into os.environ."""
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                # Ignore empty lines and comments
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value
