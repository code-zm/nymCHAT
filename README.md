
## Overview

The NymDirectory is the main server that NymCHAT clients communicate with. It allows for anonymous user / group discovery and message forwarding. 

## Features

### 1. User Registration
   - Users can register using a public key and username. During registration, the server verifies the user's identity through a signed nonce.
   
### 2. Pseudonymous Messaging
   - Users send and receive end to end encrypted messages, routed via SURB. Users just need to specify the recipient's username. 
   - The server uses SURBs to route all messages, allowing clients to never reveal nym-addresses.

### 3. Anonymous User Discovery
   - Users can anonymously query for any user or group based on username or group ID. 

## Components

### clientMonitor.py
Monitors and restarts the Nym client if it crashes or encounters an error.

### cryptographyUtils.py
Contains utility functions for cryptographic operations such as key generation, signing, and verifying messages.

### dbUtils.py
Handles interactions with the SQLite database, including user registration and group management.

### logConfig.py
Configures logging for the server, logging errors, info, and debug messages.

### messageUtils.py
Handles incoming messages, verifies signatures, processes user registration, login, sending/receiving messages, and group management.

### websocketUtils.py
Manages WebSocket communication with the Nym client and facilitates sending/receiving messages.

## Example Message Flow
1. **Client Registration**:
    - The client sends a registration request with their username, public key, and SURBs.
    - The server responds with a nonce.
    - The client signs the nonce with their private key and sends it back to the server.
    - The server verifies the signature, if successful adds user to DB. 

2. **Message Sending**:
    - The sender encrypts and signs a message for a recipient. The sender forwards this message to the directory. 

## Database Schema
The server uses an SQLite database to manage users and groups. The database schema is as follows:

- **users table**: Stores the username, public key, and sender tag for each user.
## Logging
Logs are stored in `app.log`. Detailed information about server operations, errors, and debug information are logged.

