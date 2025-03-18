## Overview

The nymDirectory is a discovery / remailer service provider used by nymCHAT clients on the Nym Mixnet. The directory stores `username -> (pubkey, senderTag)` in a local sqlite db. 

Sender tags correspond with single use reply blocks (SURB), which are received from incoming messages. SURBs allow nym-clients to reply to incoming messages without ever learning the destination of the message. 

I chose to rely strictly on SURBs because your nym-client address reveals which gateway you are connected to. 
Nym Addresses are formatted as follows:

```
<PublicIdKey>.<PublicEncryptionKey>@<GatewayIdKey>
```

Anyone with a list of gateway's can determine your gateway from the `GatewayIdKey` part of the nym address. This does not fully deanonymize you thanks to Nym's cover traffic and mixing, but it is reducing your anonymity set. An easy way around this is to use an ephemeral client (nymCHAT does by default) or manually rotate gateways often.  

By routing messages via SURB instead of nym client address, the nymDirectory enables fully pseudonymous user discovery and message forwarding. All messages are end to end encrypted by the clients to ensure the directory cannot read any message content. 

Users have the ability to route their messages directly to one another, skipping the directory entirely. To enable this, clients exchange `handshake` messages which reveal their nym addresses. All further messages can be sent directly from `client -> client`, instead of `client -> nymDirectory -> client`. The handshake data is encrypted and formatted exactly like a normal encrypted message to prevent the server from learning your nym address.  

## Components

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