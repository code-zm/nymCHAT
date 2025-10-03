# nymCHAT [ARCHIVED]

**This repository has been archived. All further development is now taking place at [github.com/nymstr](https://github.com/nymstr)**

---

A security focused messaging app powered by the Nym Mixnet. The repo is divided into two parts: the **Chat Client** (in the _client_ folder) and the **Discovery Node** (in the server folder). Together they enable pseudonymous, end-to-end encrypted messaging.

## Overview

Users register a `public key` and `username` with a discovery node. The discovery node provides user lookups & message relaying. Nodes maintain a database mapping each `username` to its corresponding `public key` and a `senderTag`. 

A `senderTag` is a random UUID string derived from received SURBs. This is used to track which received messages correspond to SURBs. Single Use Reply Blocks (SURBs) allow the server to forward messages to clients without ever knowing the destination of the message. 

Initially, messages are routed through the discovery node; however, clients can exchange an encrypted handshake to enable direct client-to-client communication for an extra layer of privacy.

## Security Properties
**I. Transport Privacy** 

All traffic routed through Nym mixnet via sphinx packet format

**II. Message Privacy**

End-to-end encryption using ECDH with ephemeral keys + AES-GCM

**III. Authentication**

Signature verification using long-term EC keys (SECP256R1)

**IV. Pseudonymity**

Username registration with no linkage to real identity

**V. Direct Communication**

Optional p2p mode bypasses discovery node after initial contact

## Quickstart
For ease of use, we recommend running the app via Docker.

Detailed documentation on building, running, and troubleshooting:

- [Client README](client/README.md)

- [Server README](server/README.md)

- [Build Docs](docs/Build.md)

For those interested in the system design, we recommend starting here:

- [Protocol Docs](docs/Protocol.md)

- [Discovery Node Overview](server/docs/Overview.md)



## Future Work
- Rust backend
- Group chats
- MLS Cryptography
- Federated network of discovery nodes
