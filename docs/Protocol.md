
**TLDR:**
- Implements a “discovery node” service that stores `(username → (public_key, senderTag))`.
- Discovery nodes challenge any new registration with a random nonce. The prospective user signs that nonce with their “username key.”
- For lookups, the discovery node queries its DB for a given `username`, if found it returns `username_pk`, else `e`.
- The contacting user obtains `username_pk` and uses it to encrypt their messages.
- All messages are forwarded through the discovery node until users decide to exchange `handshake` messages, which reveal their nym-client address. From then on, all messages for that session will be routed directly to the recipient. This is useful if you want an extra layer of privacy, as the discovery node will never know about these messages. 
- It should be noted that revealing your nym-client address reveals which gateway your client is connected to. Handshake with caution. 

## 1. Overview
Provide a privacy focused way for one user (Alice) to discover another user (Bob) using only a short username (e.g. `bob99`), rather than an email address / other real world ID.
- **Core Requirements**:

    **I. User Registration**
    
    Bob registers a username and binds it to his long‑term `SECP256R1` keypair.

    **II. Authentication**

    Bob proves ownership of that username by signing a random server‑provided nonce with his private key.

    **III. Lookups**
    
    When Alice looks up Bob’s username, she gets back Bob's associated public key. 

    **IV. SURBs**
    
    Clients send single use reply block's (SURBs) along with their `registration`, `login`, and `send` messages. The server organizes these SURBs via `senderTag`. The discovery node never needs to know the client's nym-address, and automatically updates `senderTags` as it receives new SURBs.  

    **V. Mutual Key Authentication**
    
    All client payloads are encrypted and signed to ensure other clients and the server can validate a user is who they claim to be.

    **VI. E2E Enryption**

    All messages are end to end encrypted between clients using ECDH with ephemeral keys and AES-GCM. The Discovery Node can never learn the contents of user messages. 

    **VII. Mixnet Transport**
    
    All requests and responses are carried as Sphinx packets in the Nym mixnet, preserving sender–receiver unlinkability and preventing the network from learning who’s contacting whom.


## 2. Architecture Components
![architecture diagram](../images/architecture.png)

**I. Clients**
- An application using the Nym SDK (`nym_sdk::mixnet`) via PyO3 bindings for sending and receiving mixnet messages.
- Maintains user’s long-term keypair (`username_keypair`), stored in a local on‑disk directory.
- Maintains messages and contacts locally.
- Registers a username via the discovery nodes.
- Chat UI for easy messaging.

**II. Discovery Nodes**
- Nym clients running as special-purpose application servers, each storing user registration data.
- Each node holds:
    - A database of `(username → contact info)`. (“contact info” includes user’s public key and senderTag)
- On registration, a node demands proof of ownership.
- On lookup, the node either:
    - Returns the associated `username_pk`
    - Returns an `error` message

**III. Nym Mixnet**
- Provides packet routing via the mix nodes & gateway nodes, using the standard Sphinx packet layering.
- Mixnet traffic is fully asynchronous; the user device can be offline, and the associated gateway will buffer messages.


## Protocol

`alice` wants to send a message to her friend `bob`.

**Client Registration**:

- Alice sends a registration request containing `(alice, pk_alice, SURB)` to a server.
- The server responds with a nonce.
- Alice signs the nonce and sends it back to the server.
- The server verifies the signature, if successful adds `alice -> pk_alice, senderTag` to the DB and responds with a success message.

![User Registration](../images/userLookup.png)

**User Lookup**

- Alice sends a query to the server, containing `(bob, SURB)`.
- The server receives the message and checks it's DB for `bob`.
-  If it has an entry, it forwards `PK_bob` to alice via `SURB`.
- Alice stores `bob -> PK_bob` in her local contacts table.

![User Lookup](../images/userRegistration.png)

**Message Sending**:

- Alice uses `PK_bob` and an ephemeral keypair `(SK_tmp, PK_tmp)` to derive a shared secret, then encrypts the message and encapsulates it into a payload.
- She attaches `PK_tmp` for bob to derive the same shared secret. Since this is her first message to Bob, she also attaches `PK_alice`. Alice signs the payload for Bob to verify.
- Alice then encapsulated this payload into the proper format, and signs the entire outer payload for the server to verify.
- This message is sent to the server, addressed to Bob.
- The server verifies the outer signature against Alice's stored public key and the message payload. If successful, the server queries it's local db for Bob and retrieves the associated `senderTag`.
- The server forwards the encrypted message to Bob via `SURB`.
- Bob receives the encrypted message and parses `PK_alice` and `PK_tmp` from it. Bob verifies the signature using `PK_Alice`. If successful, he uses `PK_tmp` to derive the same shared secret and decrypts the message.

![Message Sending](../images/messageSending.png)



