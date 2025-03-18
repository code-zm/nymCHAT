# nymCHAT

A privacy focused messaging app powered by the Nym Mixnet. The repo is divided into two parts: the **Chat Client** (in the _client_ folder) and the **Discovery Node** (in the server folder). Together they enable pseudonymous, end-to-end encrypted messaging.

---

## Overview

Users register a public key and username with a discovery node. The discovery node provides lookup & message relaying. Nodes maintain a database mapping each username to its corresponding public key and a `senderTag`. Sender tags are random strings derived from received SURBs. Single Use Reply Blocks (SURBs) allow the server to forward messages to clients without ever knowing the destination of the message. Initially, messages are routed through the discovery node; however, clients can exchange an encrypted handshake to enable direct client-to-client communication for an extra layer of privacy.
Looking through this codebase, I can see you've built a privacy-focused messaging system leveraging the Nym mixnet with a two-component architecture: a client application and a discovery node server. The current documentation lacks clear deployment paths, so I'll add the necessary content to the README.md.

## Quickstart 

### Docker Compose Deployment

The fastest way to deploy nymCHAT server is with Docker Compose:

```bash
# Clone the repository
git clone https://github.com/code-zm/nymCHAT.git
cd nymCHAT

# Create server configuration
cp server/.env.example server/.env
echo "your-secure-password" > server/password.txt
chmod 600 server/password.txt

# Deploy with docker-compose
docker-compose up -d
```

This deploys the discovery node server. The docker-compose configuration:
- Builds the server container with the required dependencies
- Mounts persistent volumes for Nym identity and database
- Runs the `install.sh` script to set up the Nym client
- Executes the server application that handles message routing

### Local Development Setup

#### Server Setup

```bash
# 1. Set up a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install server dependencies
cd server
pip install -r requirements.txt  # Or: uv pip install -r requirements.txt

# 3. Configure the server
cp .env.example .env
echo "your-secure-password" > password.txt
chmod 600 password.txt

# 4. Set up the Nym client binary

# on MacOS try this script for automated build 
# it installs Rust, all tools needed with user prompts
# You will need to have Brew installed obviously.
curl -fsSL https://raw.githubusercontent.com/dial0ut/nym-build/main/nym_build.sh | bash

# 5. Initialize Nym client 
~/.local/bin/nym-client init --id nym_server
# 6. Run the server
python src/mainApp.py
```

#### Client Setup

```bash
# 1. Set up a virtual environment if not already done
cd client
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install Python dependencies
pip install nicegui cryptography  # Or: uv pip install nicegui cryptography
# 3. Build the Rust FFI component
cd async_ffi
cargo build --release
# 4. Create a config file

echo "SERVER_ADDRESS=<your_server_nym_address>" > .env

# 5. Run the client
cd ..
python src/runClient.py
```

## Architecture Overview

nymCHAT implements a pseudonymous message routing system with two key components:

1. **Discovery Node Server**: 
   - Manages username → (public_key, senderTag) mappings
   - Handles user registration with cryptographic challenge-response
   - Routes messages between clients via ephemeral SURB channels
   - Never learns message content due to end-to-end encryption

2. **Client Application**:
   - NiceGUI-based frontend 
   - Uses ECDH + AES-GCM for end-to-end message encryption
   - Implements ephemeral "handshake" protocol for direct p2p routing
   - Stores contacts and messages in SQLite database

### Security Properties

- **Transport Privacy**: All traffic routed through Nym mixnet with sphinx packet format
- **Message Privacy**: End-to-end encrypted using ECDH with ephemeral keys + AES-GCM
- **Authentication**: Signature verification using long-term EC keys (SECP256R1)
- **Pseudonymity**: Username registration with no linkage to real identity
- **Direct Communication**: Optional p2p mode bypasses discovery node after initial contact

1. **Container Integration**: Builds the server container directly from the Dockerfile in the server directory, handling environment configuration and service startup.

2. **Volume Management**: Three critical mount points:
   - `nym-data`: Preserves Nym client identity across restarts
   - `storage`: Maintains the database and logs
   - `secrets`: Secures encryption passwords

3. **Port Exposure**: Exposes port 1977 for WebSocket communication with the Nym client.

4. **Health Monitoring**: Implements a health check to verify service operation.

For full deployment, you should add this file to your repository and update your documentation to reference it. This approach isolates the server component while maintaining the persistent state needed for the discovery node to function properly.

The client component was intentionally excluded from the Docker setup as it's a GUI application that users would typically run locally rather than in a container.
---

## Protocol

`alice` wants to send a message to her friend `bob`.

**Client Registration**:

- Alice sends a registration request containing `(alice, pk_alice, SURB)` to a server.
- The server responds with a nonce.
- Alice signs the nonce and sends it back to the server.
- The server verifies the signature, if successful adds `alice -> pk_alice, senderTag` to the DB and responds with a success message.

**User Lookup**

- Alice sends a query to the server, containing `(bob, SURB)`.
- The server receives the message and checks it's DB for `bob`.
-  If it has an entry, it forwards `PK_bob` to alice via `SURB`.
- Alice stores `bob -> PK_bob` in her local contacts table.

**Message Sending**:

- Alice uses `PK_bob` and an ephemeral keypair `(SK_tmp, PK_tmp)` to derive a shared secret, then encrypts the message and encapsulates it into a payload.
- She attaches `PK_tmp` for bob to derive the same shared secret. Since this is her first message to Bob, she also attaches `PK_alice`. Alice signs the payload for Bob to verify.
- Alice then encapsulated this payload into the proper format, and signs the entire outer payload for the server to verify.
- This message is sent to the server, addressed to Bob.
- The server verifies the outer signature against Alice's stored public key and the message payload. If successful, the server queries it's local db for Bob and retrieves the associated `senderTag`.
- The server forwards the encrypted message to Bob via `SURB`.
- Bob receives the encrypted message and parses `PK_alice` and `PK_tmp` from it. Bob verifies the signature using `PK_Alice`. If successful, he uses `PK_tmp` to derive the same shared secret and decrypts the message.

---

## TODO

- Group chats
- MLS Cryptography
- Federated network of discovery nodes
