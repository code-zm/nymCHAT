` ### IN PROGRESS ### `

TLDR:
- Implements a “discovery node” service that stores `(username → (public_key, senderTag))`.
- Discovery nodes challenge any new registration with a random nonce. The prospective user signs that nonce with their “username key.”
- For lookups, the discovery node queries its DB for a given `username`, if found it returns `username_pk`, else `e`
- The contacting user obtains `username_pk` and uses it to encrypt their messages.
- All messages are forwarded through the discovery node until users decide to exchange `handshake` messages, which reveal their nym-client address. From then on, all messages for that session will be routed directly to the recipient. This is useful if you want an extra layer of privacy, as the discovery node will never know about these messages. 
- It should be noted that revealing your nym-client address reveals which gateway your client is connected to. Handshake with caution. 

---

## 1. Overview

- **Goal**: Provide a privacy oriented way for one user (Alice) to discover another user (Bob) using only a short username (e.g. `bob99`), rather than an email address / other real world ID.
- **Core Requirements**:
    1. User Registration: Bob registers a username and binds it to his long‑term keypair.
    2. Authentication: Bob proves ownership of that username by signing a random server‑provided nonce with his private key.
    3. Lookups: When Alice looks up Bob’s username, she gets back Bob's associated public key. 
    4. SURBs: Clients send single use reply block's (SURBs) along with their `registration`, `login`, and `send` messages. The discovery node never needs to know the client's nym-address.   
    4. Mutual Key Authentication: All client payloads are encrypted and signed to ensure other clients and the server can validate a user is who they claim to be.
    5. Mixnet Transport: All requests and responses are carried as Sphinx packets in the Nym mixnet, preserving sender–receiver unlinkability and preventing the network from learning who’s contacting whom.


## 2. Architecture Components
1. **Clients**
    - An application using the Nym SDK (`nym_sdk::mixnet`) for sending and receiving mixnet messages.
    - Maintains user’s long-term keypair (`username_keypair`), stored in a local on‑disk directory.
    - Registers a username via the discovery nodes.
    - Chat UI for easy messaging.
2. **Discovery Nodes**
    - Nym clients running as special-purpose application servers, each storing user registration data.
    - Each node holds:
        - A database of `(username → contact info)`. (“contact info” includes user’s public key and senderTag)
    - On registration, a node demands proof of ownership.
    - On lookup, the node either:
        - Returns the associated `username_pk`
        - Returns an `error` message
3. **Nym Mixnet**
    - Provides packet routing via the mix nodes & gateway nodes, using the standard Sphinx packet layering.
    - Mixnet traffic is fully asynchronous; the user device can be offline, and the associated gateway will buffer messages.


## 3. Protocol
Alice wants to send a message to her friend Bob. 

**Client Registration**:
- Alice sends a registration request containing `alice, pk_alice, senderTag` to a server.
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
- The server verifies the outer signature against Alice's stored public key and the entire message payload. If successful, the server queries it's local db for Bob and retrieves associated `PK_bob` and `senderTag`.
- The server forwards the encrypted message to Bob via SURB.
- Bob receives the encrypted message and parses the keys from it. Bob verifies the inner signature against Alice's public key and the encrypted payload. If successful, he derives the same shared secret and decrypts the message. 

