## Quickstart 

### Docker Compose Deployment

The fastest way to deploy both the discovery node & client is with Docker Compose:

```bash
# Clone the repository
git clone https://github.com/code-zm/nymCHAT.git
cd nymCHAT

# Create server configuration
cp server/.env.example server/.env
echo "your-secure-password" > server/password.txt
chmod 600 server/password.txt

# Deploy with docker-compose
docker compose up --build -d
```

This deploys the discovery node server and client, with the client automatically configured to use your discovery node. The docker-compose configuration:
- Builds the server container with the required dependencies
- Mounts persistent volumes for Nym identity and database
- Runs the `install.sh` script to set up the Nym client
- Executes the server application that handles message routing

### Building from Source

#### Server Setup

Note: need the `nym-client` binary installed, if you're on linux based os this can be installed directly from https://github.com/nymtech/nym/releases/

If running on mac, try this installation script. 
You will need to have Brew installed.

```
curl -fsSL https://raw.githubusercontent.com/dial0ut/nym-build/main/nym_build.sh | bash
```


```bash
# 1. Set up a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install server dependencies
cd server
pip install -r requirements.txt  # Or: uv pip install -r requirements.txt

# 3. Configure the server
cp .env.example .env
echo "your-secure-password" >> password.txt
chmod 600 password.txt

# 4. Set up the Nym client binary


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
pip install -r requirements.txt  # Or: uv pip install nicegui cryptography
# 3. Build the Rust FFI component
cd async_ffi
maturin build --release
# 4. Set the discovery node address
cp .env.example .env # Note: the address in the .env.example is the official nymCHAT discovery node

# 5. Run the client
cd ..
python src/runClient.py
```

---

## Docker Compose Deployment Architecture

In this section we will cover the containerization of our current application. 
Prepare for a deep-dive into the world of 1337. 

It should also cover the some issues you might encounter during the setup, so we also added a Troubleshooting section.


### High-level overview 

Our Docker Compose configuration establishes a seamless deployment of both the server and client components with appropriate isolation and communication channels.

### Network and Service Communication

The deployment uses a bridge network (`nym_network`) to isolate the application's internal communication. The critical connection flow works as follows:

1. The server initializes a Nym client and writes its address to `/app/shared/nym_address.txt`
2. The client container waits for this file to appear, then reads the server's address
3. This address is used by the client to establish a connection to the discovery node

### Volume Structure and Data Sharing

The architecture leverages Docker volumes for persistence and inter-service communication:

- `server_data`: Stores server-specific data (SQLite DB and encryption keys)
- `server_nym_data`/`client_nym_data`: Separate Nym identities for server and client 
- `client_data`: Client-specific storage for local databases
- `address_data`: Critical shared volume mounted at `/app/shared` in both containers

The shared address volume creates a simple yet effective communication channel between containers without exposing sensitive information through environment variables or command-line arguments.

### Troubleshooting Container Networking

If you experience networking issues between containers:

1. Test basic connectivity using Netcat:
   ```bash
   # Test if ports are reachable on your host machine (old h4x0r  way)
   ncat localhost 1977 -v # this should show you some open socket, if you see connx timed out, something is wrong.
   ncat localhost 8080 -v # if the webUI is working, you should get the same result. 
   HEAD / HTTP/1.1 # smash enter until server responds 
   # Install netcat in a container if needed
   docker compose exec server apk add --no-cache netcat-openbsd
   
   # From server, verify client is reachable (replace PORT with the internal port)
   docker compose exec server nc -zv client PORT
   
   # From client, verify server is reachable
   docker compose exec client nc -zv server 2000
   ```

2. Verify the shared address file exists:
   ```bash
   docker-compose exec server cat /app/shared/nym_address.txt
   docker-compose exec client cat /app/shared/nym_address.txt
   ```

3. Check container logs for specific errors:
   ```bash
   docker compose logs server
   docker compose logs client
   ```

4. Verify volume mounts are working correctly:
   ```bash
   docker compose exec server ls -la /app/shared
   docker compose exec client ls -la /app/shared
   ```

### Container Startup Sequence

The containers follow a specific startup sequence:

1. `server-init` creates the necessary storage structure and encryption password
2. `server` starts and initializes its Nym client, writing the address to the shared volume
3. The `client` container waits until the server health check passes (address file exists)
4. The client reads the server address and establishes connection to the mixnet

**This orchestrated startup ensures the client always has the correct server address before attempting connection.**

Hopefully, this explanation can explain everything you need to know about the details on how the networking architecture works, why volumes are shared between containers, and how to troubleshoot common issues. 

