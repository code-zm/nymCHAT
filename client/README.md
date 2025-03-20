## Docker Build

Build:
```
docker build -t nymchat:latest .
```

Run:
```
docker run -d -p 8080 -v $(pwd)/storage:/app/storage --name nymchat-client nymchat:latest
```

Check logs:
```
docker logs -f nymchat-client
```


---
## Build from Source 

Prerequisites
- Python 3.11
- Rust
---
## Set Up  

1.  Clone this repository and navigate to the directory:
```
git clone https://github.com/code-zm/nymCHAT.git
cd client
```

2. Create & activate python virtual environment
```
python3 -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\activate
```

3. Install requirements
```
pip install -r requirements.txt
```

4. Build the python-rust bindings
```
cd async_ffi # change to the rust ffi directory 
maturin build --release # build the .whl
```
*Take note of where the .whl file is built, usually `/target/wheels/`*

5. Install the FFI library
```
pip install target/wheels/*.whl
```

---
## Running the App

```
cd .. # go back to the client home directory
python src/runClient.py # launch the client
```

--- 
## Usage
**Connect to the mixnet**
	- Start the app
	- Connect to the mixnet

 **Register a new user**:
    - Navigate to the **Register** page, enter your username, and click **Register**.
    - The system will generate a key pair and send a registration request to the NymDirectory server.

**Login**:
    - After registration, log in using your username to access the messaging features.

**Search**
	- To start a chat with a new user, click the search button at the top. 
	- Enter the username and click search. *Note: Usernames are CASE SENSITIVE*

**Send Messages**:
    - Once logged in, you can select a contact and send secure, encrypted messages.

**Send Handshake**:
	- Send a handshake to allow the recipient to route their messages directly to you instead of through the discovery node. 

**Database Storage**:
    - All messages are stored locally in a SQLite database. The app loads your messages upon login and stores new ones after each communication.

--- 
## Script Overview

- `connectionUtils.py`: Manages Mixnet operations using Rust-Python FFI library.
- `cryptographyUtils.py`: Handles cryptographic operations like key generation, signing, encryption, and decryption.
- `dbUtils.py`: Manages the local SQLite database for contacts and messages.
- `messageHandler.py`: Handles the logic for registering, logging in, and managing messages.
- `mixnetMessages.py`: Constructs messages for communication with `nym-client`.
- `runClient.py`: Runs the user interface using NiceGUI.
- `storage/`: Directory where keys and databases are stored.
- `client/`: Directory where the scripts are stored. 
