` ### IN PROGRESS ### `

TLDR:
Based on the Pudding Protocol: https://arxiv.org/abs/2311.10825
- Implements a “discovery node” service that stores `(username → (public_key, nym_address))`.
- Discovery nodes challenge any new registration with a random nonce. The prospective user signs that nonce with their “username key.”
- For lookups, the discovery node produces a deterministic SURB so the user doesn’t learn membership from a “no such user” error.
- The contacting user obtains `f+1` consistent SURBs from the nodes (protecting from malicious replies) and uses the real or fake SURB to attempt contact.
- Finally, the contacted user can reply or ignore.

---

## 1. Overview

- **Goal**: Provide a metadata-private means for one user (Alice) to discover another user (Bob) using only a short username (e.g. `bob99`), rather than an email address / other real world ID.
- **Core Requirements**:
    1. **User Registration**: Bob registers a username and binds it to his long‑term keypair, stored in his local Nym client.
    2. **Authentication**: Bob proves ownership of that username by signing a random server‑provided nonce with his private key.
    3. **Lookups & SURBs**: When Alice looks up Bob’s username, she gets back a _single‑use reply block_ (SURB) and Bob’s associated authentication material—but only if Bob is registered. If Bob does not exist in the registry, the server nodes return a _fake SURB_ (so an unregistered username is indistinguishable from a user that chooses not to reply).
    4. **Hidden Membership**: A malicious user should not be able to query the discovery service and confirm if a certain username is registered (the “membership unobservability” property).
    5. **Mutual Key Authentication**: If Bob wants to confirm that Alice’s request really comes from the user who claims to own `alice01`, Alice similarly signs a challenge from Bob with her private key.
    6. **Mixnet Transport**: All discovery queries and responses are carried as Sphinx packets in the Nym mixnet, preserving sender–receiver unlinkability and preventing the network from learning who’s contacting whom.

---

## 2. Architecture Components
1. **Client (User Device)**
    - An application using the Nym SDK (`nym_sdk::mixnet`) for sending and receiving mixnet messages.
    - Maintains user’s long-term keypair (`username_keypair`), stored either in a local on‑disk directory.
    - Registers a username via the discovery nodes.
    - Chat UI for easy messaging.
2. **Discovery Nodes (Byzantine Fault Tolerant)**
    - Nym clients running as special-purpose application servers, each storing full user registration data.
    - Each node holds:
        - A database of `(username → contact info)`. (“contact info” includes user’s public key, plus any Nym routing data needed.)
        - A secret `k` shared across discovery nodes for **deterministic SURB generation**.
    - On registration, a node demands proof of ownership (the server challenges the user to sign a random nonce).
    - On lookup, the node either:
        - Returns a deterministic SURB for the real user (if registered), or
        - Returns a fake SURB that routes nowhere (“black‑hole” route) to conceal membership.
    - The system requires at least `3f+1` nodes to tolerate `f` Byzantine nodes.
3. **Nym Mixnet**
    - Provides packet routing via the mix nodes & gateway nodes, using the standard Sphinx packet layering.
    - The mixnet traffic is fully asynchronous; the user device can be offline, and the associated gateway buffers messages.

---

## 3. Data Structures & Keys
1. **Username Keypair**
    - Generated on the user’s device upon first use: `(pk_u, sk_u)`.
    - A user chooses a short username string (e.g. `bob99`) and will bind `(username, pk_u)`.
2. **Discovery Node Keys**
    - Each discovery node has its own private signing key for any response messages it must send.
    - The set of `n` discovery nodes shares a secret `k` that seeds their _deterministic SURB generation_.
3. **SURB** (Single-Use Reply Block)
    - Contains an _onion‑encrypted_ route (header + keys) that will send a message back to a _specific contact info_ without revealing that contact info to the sender.
    - In standard Nym code, see `nym_sphinx_types::SURB` and the `ReplySurb` struct in `reply_surb.rs`.
4. **Fake SURB (FURB)**
    - Created by substituting a fake “black‑hole” public key into the SURB generation.
    - Discovery nodes ensure the black‑hole key is chosen so that no party can decrypt or route it.

---

## 4. Protocol Flow
#### 4.1 Registration Phase
1. **User Generates Keys**
    - On Bob’s device:
```rust
let (pk_bob, sk_bob) = generate_long_term_keys();
let bob_username = "bob99".to_owned();
```

> This keypair is distinct from the standard Nym identity key. It is specifically for username authentication

2. **Challenge–Response with Discovery Nodes**
    - Bob picks _any_ discovery node to contact and sends a _register_ request, containing `(bob_username, pk_bob)`.
    - The discovery node randomly generates a nonce and sends it back to Bob.
    - Bob signs the nonce
    - Bob returns `(bob_username, pk_bob, signature)` to the node.
    - The node checks that `signature` verifies under `pk_bob`. If correct, it records `(bob_username → pk_bob, nym_contact_info)` in its database.
3. **Broadcast to other Discovery Nodes**
    - The node replicates `(bob_username → pk_bob, nym_address)` to all other discovery nodes
```
#TODO
```

### 4.2 Discovery Phase 
1. **Alice Sends Lookup**
    - Alice creates a random `lookup_nonce` and a SURB (`surb_A`) that points back to her. She sends `(bob_username, lookup_nonce, surb_A)` to x discovery nodes via the mixnet.
    - Each discovery node checks:
        - If `bob_username` is in its database, it obtains `(pk_bob, nym_address)`.
        - If absent, it uses a black‑hole ID `∆fake`.
2. **Deterministic SURB Generation**
    - Each node uses `K = KDF(k, bob_username, lookup_nonce)` as the PRNG seed.
    - If `bob_username` is found, it calls
```rust
let surb_for_bob = deterministic_surb(     
	&nym_address, // pk_bob, gateway addr, etc.     
	K );
```   

Otherwise, it calls
```rust
let surb_for_bob = deterministic_surb(    
	&fake_contact_info, // black-hole     
	K );
```

It returns `(lookup_nonce, surb_for_bob, node_signature)` to Alice using her SURB `surb_A`.

3. **Alice Validates**
    - Once she collects `f+1` identical `(surb_for_bob, lookup_nonce)` from distinct nodes, she trusts that SURB.
    - (She also gets a _blinding key_ or _node signature_ if you implement the “key-blinded signatures” approach from Pudding for membership unobservability.)
4. **Discovery Node → Bob** (Optional “Heads-Up”)
    - The node can also send Bob the _blinding key_ or a new challenge, letting Bob see who’s searching for him—depending on whether you want Bob to approve being found. This parallels the Pudding “CONTACTINIT” step.

### 4.3 Contact Initialization (Alice → Bob)

1. **Alice Sends Initial Message via SURB**
    - Alice wants to inform Bob, “Hi, I’m Alice,” or remain pseudonymous.
    - She encrypts her ephemeral key or codeword to Bob under the ephemeral key agreement. If she wants to prove she really is `alice01`, she can sign Bob’s challenge.
    
2. **Bob’s Receipt & Verification**
    - Bob’s client sees the incoming message. 
    - Verifies the signature from Alice’s private key matches `alice01`.
    
3. **Bob → Alice**
    - If Bob decides to respond, he can use the _SURB included by Alice_ or simply use her contact info if she revealed it. They can establish an authenticated channel from that point on.

## 5. Putting It All Together
A succinct outline of the full flow:

1. **User Registration**
    1. Bob uses an _authentication keypair_ distinct from the standard Nym identity.
    2. Bob connects to a discovery node via the mixnet and sends `(register, bob_username, pk_bob)`.
    3. Node sends back a challenge `nonce_server`.
    4. Bob signs it with `sk_bob → signature_bob`.
    5. Node verifies & stores `(bob_username → nym_address, pk_bob)`.

2. **User Discovery**
    1. Alice obtains a fresh `lookup_nonce` and a SURB `surb_A` to get replies.
    2. She sends `(bob_username, lookup_nonce, surb_A)` to each discovery node.
    3. Each node:
        - Looks up `(bob_username → pk_bob, nym_address)` or uses a black‑hole identity.
        - Creates a _deterministic SURB for Bob_, or a _fake SURB_, both seeded by `K = KDF(k, bob_username, lookup_nonce)`.
        - Returns that SURB to Alice via `surb_A`.
    4. Alice collects `f+1` identical SURBs → uses that route to reach Bob.

3. **Initial Contact**
    1. Using the returned “real” SURB (if it is real), Alice sends an encrypted message to Bob with an ephemeral key or a signature proving her own username.
    2. Bob verifies Alice’s proof as needed, and they establish an authenticated session. If Bob is offline initially, the gateway buffers messages.

By combining challenge/response signatures for user verification with the Nym mixnet's capabilites, we get a Pudding-style protocol that uses short usernames and a simple cryptographic proof of ownership (signing a server-provided nonce) rather than email validation. 
