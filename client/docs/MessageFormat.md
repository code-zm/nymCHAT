
**General Message Format**
```json
{
  "a": "action_code",
  "c": "context_code", 
  "p": "{payload}"
}
```

This is then encapsulated for the nym-client to send, resulting in this nested  structure:
```json
{
  "message": "{\"a\":5,\"p\":{\"f\":\"alice\",\"to\":\"bob\",\"e\":{\"epk\":\"<ephemeral_pubkey>\",\"iv\":\"<initialization_vector>\",\"ct\":\"<ciphertext>\",\"tag\":\"<auth_tag>\"},\"s\":\"<signature_of_payload>\"}}",
  "recipient": "recipient_nym_address",
  "senderTag": "sender_tag"
}
```


## Client -> Server Messages

#### 🔍 Query User (Action = 0)
Query the server for user information (public key).

```
# Inner Payload
{
  "u": "<target_username>"
}

# Full Message
{
  "message": "{ 
    \"a\": 0,
    \"p\": {
      \"u\": \"bob\"
    }
  }",
  "recipient": "server_address_here",
  "senderTag": "client_sender_tag"
}
```

#### 🔑 Register (Action = 1)
Registers a new user account.

```
# Inner Payload
{
  "u": "<username>",
  "k": "<user_public_key_PEM>"
}

# Full Message
{
  "message": "{ 
    \"a\": 1,
    \"p\": {
      \"u\": \"alice\",
      \"k\": \"<user_public_key_PEM>\"
    }
  }",
  "recipient": "server_address_here",
  "senderTag": "client_sender_tag"
}
```

#### 📤 Registration Response (Action = 2)
Client responds to registration challenge.

```
# Inner Payload
{
  "u": "<username>",
  "s": "<signature_of_nonce>"
}

# Full Message
{
  "message": "{ 
    \"a\": 2,
    \"p\": {
      \"u\": \"alice\",
      \"s\": \"<signature_of_nonce>\"
    }
  }",
  "recipient": "server_address_here",
  "senderTag": "client_sender_tag"
}
```

#### 🔐 Login (Action = 3)
Request to authenticate an existing user.


```
# Inner Payload
{
  "u": "<username>"
}

# Full Message
{
  "message": "{ 
    \"a\": 3,
    \"p\": {
      \"u\": \"alice\"
    }
  }",
  "recipient": "server_address_here",
  "senderTag": "client_sender_tag"
}


```

#### ✅ Login Response (Action = 4)
Client responds to a login challenge.


```
# Inner Payload
{
  "u": "<username>",
  "s": "<signature_of_nonce>"
}

# Full Message:
{
  "message": "{ 
    \"a\": 4,
    \"p\": {
      \"u\": \"alice\",
      \"s\": \"<signature_of_nonce>\"
    }
  }",
  "recipient": "server_address_here",
  "senderTag": "client_sender_tag"
}

```

#### 📧 Send Direct Message (Action = 5)
Sends an encrypted direct message to another user.

```
# Inner Payload
{
  "f": "<sender_username>",
  "to": "<recipient_username>",
  "e": {
    "epk": "<ephemeral_pubkey>",
    "iv": "<initialization_vector>",
    "ct": "<ciphertext>",
    "tag": "<auth_tag>"
  },
  "s": "<signature_of_payload>"
}

# Full Message
{
  "message": "{ 
    \"a\": 5,
    \"p\": {
      \"f\": \"alice\",
      \"to\": \"bob\",
      \"e\": {
        \"epk\": \"<ephemeral_pubkey>\",
        \"iv\": \"<initialization_vector>\",
        \"ct\": \"<ciphertext>\",
        \"tag\": \"<auth_tag>\"
      },
      \"s\": \"<signature_of_payload>\"
    }
  }",
  "recipient": "server_address_here",
  "senderTag": "client_sender_tag"
}
```


## Server -> Client Messages

#### 🔍 Query Response (Action = 0)
Server response to a user's query request.

Context required:
- `c: 3` (Query)

If user found:
```

# Inner Payload
{
  "u": "<username>",
  "k": "<user_public_key_PEM>"
}

# Full Message
{
  "message": "{ 
    \"a\": 0,
    \"c\": 3,
    \"p\": {
      \"u\": \"bob\",
      \"k\": \"<user_public_key_PEM>\"
    }
  }",
  "recipient": "client_ephemeral_address",
  "senderTag": "server_sender_tag"
}
```

If user not found:
```
# Inner Payload
"No user found"

# Full Message
{
  "message": "{ 
    \"a\": 0,
    \"c\": 3,
    \"p\": \"No user found\"
  }",
  "recipient": "client_ephemeral_address",
  "senderTag": "server_sender_tag"
}
```

#### 📥 Incoming Message (Action = 6)
Encrypted direct message forwarded from another client via server.

Context required:
- `c: 2` (Chat)

Payload:
```

# Inner Payload
{
  "f": "<sender_username>",
  "e": {
    "epk": "<ephemeral_pubkey>",
    "iv": "<initialization_vector>",
    "ct": "<ciphertext>",
    "tag": "<auth_tag>"
  },
  "s": "<signature_of_payload>",
  "pk": "<sender_public_key_optional>"
}

# Full Message
{
  "message": "{ 
    \"a\": 6,
    \"c\": 2,
    \"p\": {
      \"f\": \"alice\",
      \"e\": {
        \"epk\": \"<ephemeral_pubkey>\",
        \"iv\": \"<initialization_vector>\",
        \"ct\": \"<ciphertext>\",
        \"tag\": \"<auth_tag>\"
      },
      \"s\": \"<signature_of_payload>\",
      \"pk\": \"<sender_public_key_optional>\"
    }
  }",
  "recipient": "bob_ephemeral_address",
  "senderTag": "sender_ephemeral_tag"
}
```

#### 📦 Send Response (Action = 7)
Server acknowledges the delivery status of a client's sent message.

Context required:
- `c: 2` (Chat)

- on success:
```
# Inner Payload
"success"

# Full Message
{
  "message": "{ 
    \"a\": 7,
    \"c\": 2,
    \"p\": \"success\"
  }",
  "recipient": "client_ephemeral_address",
  "senderTag": "server_sender_tag"
}
```

- on fail:
```
# Inner Payload
"error:<reason>"

# Full Message
{
  "message": "{ 
    \"a\": 7,
    \"c\": 2,
    \"p\": \"error:recipient not found\"
  }",
  "recipient": "client_ephemeral_address",
  "senderTag": "server_sender_tag"
}
```

#### 🛡️ Challenge (Action = 8)
Sends a cryptographic nonce challenge to verify identity.

Contexts required:
- `c: 0` (Registration)
- `c: 1` (Login)

Payload:
```
{
  "n": "<nonce>"
}
```

#### ✅ Challenge Response (Action = 9)
Server confirms client's response to a challenge.

Contexts required:
- `c: 0` (Registration)
- `c: 1` (Login)

Payload:
- on success:
```
"success"
```

- on fail:
```
"error:<reason>"
```


## Client -> Client Direct Messages
#### 📬 Incoming Direct Message (Action = 6)
Direct encrypted messages sent between clients via ephemeral routing. The recipient client receives this format directly:

Context required:
- `c: 2` (Chat)

```
# Inner Payload
{
  "f": "<sender_username>",
  "e": {
    "epk": "<ephemeral_pubkey>",
    "iv": "<initialization_vector>",
    "ct": "<ciphertext>",
    "tag": "<auth_tag>"
  },
  "s": "<signature_of_payload>",
  "pk": "<sender_public_key_optional>"
}

# Full Message
{
  "message": "{ 
    \"a\": 6,
    \"c\": 2,
    \"p\": {
      \"f\": \"alice\",
      \"e\": {
        \"epk\": \"<ephemeral_pubkey>\",
        \"iv\": \"<initialization_vector>\",
        \"ct\": \"<ciphertext>\",
        \"tag\": \"<auth_tag>\"
      },
      \"s\": \"<signature_of_payload>\",
      \"pk\": \"<sender_public_key_optional>\"
    }
  }",
  "recipient": "bob_ephemeral_address",
  "senderTag": "sender_ephemeral_tag"
}
```

# 📖 References:

**Field Legend**

| Field | Description                                     |
| ----- | ----------------------------------------------- |
| `a`   | Action code                                     |
| `c`   | Context code                                    |
| `p`   | Payload                                         |
| `u`   | Username                                        |
| `k`   | Public key (PEM format)                         |
| `s`   | Signature                                       |
| `n`   | Nonce                                           |
| `f`   | Sender username ("from")                        |
| `to`  | Recipient username                              |
| `e`   | Encrypted payload                               |
| `epk` | Ephemeral public key                            |
| `iv`  | Initialization vector (base64)                  |
| `ct`  | Ciphertext (base64)                             |
| `tag` | AES-GCM authentication tag (base64)             |
| `pk`  | Sender's public key (optional, initial contact) |

 **🗂️ Action Codes Reference Table**

| Action Name           | Code |
| --------------------- | ---- |
| Query User            | 0    |
| Register              | 1    |
| Registration Response | 2    |
| Login                 | 3    |
| Login Response        | 4    |
| Send Direct Message   | 5    |
| Incoming Message      | 6    |
| Send Response         | 7    |
| Challenge             | 8    |
| Chellenge Response    | 9    |

**🏷️ Context Codes Reference Table**

|Context Name|Code|
|---|---|
|Registration|0|
|Login|1|
|Chat|2|
|Query|3|
