# Nym Discovery Node (Rust)

A discovery and message relay service for nymCHAT clients, fully rewritten in Rust using the Nym Mixnet SDK.

## Configuration

Copy the example environment file, create a secrets directory, and provide your encryption password:

```bash
cp .env.example .env
mkdir -p secrets logs
echo "your-secure-password" > secrets/encryption_password
chmod 600 secrets/encryption_password
```

Edit `.env` to customize any of the following variables:

- `NYM_CLIENT_ID`: Unique identifier for this discovery node.
- `NYM_SDK_STORAGE`: Path to the Nym SDK storage directory (defaults to `storage/${NYM_CLIENT_ID}` if unset).
- `DATABASE_PATH`: Path to the SQLite database file.
- `KEYS_DIR`: Directory for user encryption keys.
- `SECRET_PATH`: Path to the file containing your encryption password.
- `LOG_FILE_PATH`: File path for log output.

## Running Locally

Ensure you have Rust toolchain installed, then:

```bash
cargo run --release
```

This will start the discovery node, connect to the Nym Mixnet, and begin processing incoming messages.

## Environment Variables

See `.env.example` for details on required variables.

## License

This project is licensed under the Apache-2.0 License.