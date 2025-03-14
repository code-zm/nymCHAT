## Overview

The nymDirectory is a discovery / remailer service provider used by nymCHAT clients. The directory stores `username -> (pubkey, senderTag)` in a local sqlite db. 

Sender tags correspond with single use reply blocks, which are received from incoming registration / login messages. Single use reply blocks allow nym-clients to reply to incoming messages without ever learning the final destination of the message. We chose to rely strictly on SURBs because your nym-client address reveals which gateway you are connected to. This is ~kind of~ doxxing yourself, as anyone who knows your nym address can easily get the IP address of the gateway that your client is connected to. This does not fully deanonymize you thanks to cover traffic and mixing, but it is reducing your anonymity set to one node. 

By routing messages via SURB instead of nym client address, we allow fully pseudonymous user discovery and message forwarding. All messages are end to end encrypted by the clients to ensure the server cannot read any message content. Clients also have the ability to send a `handshake` message which reveals their nym address to the intended recipient, allowing all further messages to be sent directly from `client -> client`, instead of `client -> nymDirectory -> client`. The handshake data is encrypted and formatted exactly like a normal encrypted message to prevent the server from learning your nym address.  


## Features

**User Registration**
   - Users can register using a public key and username. During registration, the server verifies the user's identity through a signed nonce.

**Pseudonymous Messaging**
   - Users send and receive end to end encrypted messages through the nymDirectory by specifying the recipient's username. 
   - The server forwards messages via SURBs. Never learning the addresses of sender or recipient. 

**Privacy Preserving User Discovery**
   - Users can anonymously query for any user who is registered with the nymDirectory. 


## Protocol
Alice wants to send a message to her friend Bob.

**Client Registration**:
- Alice sends a registration request containing `alice, pk_alice, senderTag`.
- The server responds with a nonce.
- Alice signs the nonce and sends it back to the server.
- The server verifies the signature, if successful adds `alice -> pk_alice, senderTag` to the DB and responds with a success message. 

**User Lookup**
- Alice sends a query to the server, containing a target username `bob` and `senderTag`. 
- The server receives the message and stores the attached `senderTag` in memory. 
- Server checks it's db for `bob`, if it has an entry, sends a queryResponse to the attached senderTag containing `PK_bob`.
- Alice stores `bob -> PK_bob` in her local contacts table. 

 **Message Sending**:
- Alice uses `PK_bob` and an ephemeral keypair `SK_tmp, PK_tmp` to derive a shared secret, then encrypts the message using it.
- Alice signs the encrypted payload for Bob to verify. She attaches `PK_tmp` for bob to derive the same shared secret. Since this is her first message to Bob, she also attaches `PK_alice`. 
- Alice signs the entire outer payload for the server to verify. 
- This message is sent to the server, addressed to Bob.  
- The server verifies the outer signature against Alice's stored public key and the entire message payload. If successful, the server queries it's local db for Bob and retrieves the stored senderTag.
- The server forwards the encrypted message to Bob via SURB.
- Bob receives the encrypted message and parses the keys from it. Bob verifies the inner signature against Alice's public key and the encrypted payload. If successful, he derives the same shared secret and decrypts the message. 


## Components

**clientMonitor.py**
Monitors and restarts the Nym client binary if it crashes or encounters an error.

**cryptographyUtils.py**
Contains utility functions for cryptographic operations such as key generation, signing, and verifying messages.

**dbUtils.py**
Handles interactions with the SQLite database, including user registration and group management.

**logConfig.py**
Configures logging for the server, logging errors, info, and debug messages.

**messageUtils.py**
Handles incoming messages, verifies signatures, processes user registration, login, sending/receiving messages.

**websocketUtils.py**
Manages WebSocket communication with the Nym client binary and facilitates sending/receiving messages from the mixnet.