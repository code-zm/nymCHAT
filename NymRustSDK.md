[[programming]], [[documentation]], [[nym]]
## Installation

The `nym-sdk` crate is **not yet available via [crates.io(opens in a new tab)](https://crates.io/)**. As such, in order to import the crate you must specify the Nym monorepo in your `Cargo.toml` file. Since the `HEAD` of `master` is always the most recent release, we recommend developers use that for their imports, unless they have a reason to pull in a specific historic version of the code.

```
# importing HEAD of master branch
nym-sdk = { git = "https://github.com/nymtech/nym", branch = "master" }
# importing HEAD of the third release of 2023, codename 'kinder'
nym-sdk = { git = "https://github.com/nymtech/nym", branch = "release/2023.3-kinder" }
```

Work will occur in the future to break the monorepo down into importable features, in order to reduce the number of dependencies imported by developers.

## Mixnet Module

This module exposes the logic of creating and interacting with clients and Mixnet messages. This is recommended for those wanting to either start playing around with the Mixnet and how it works, or build connection logic.


## Simple Send

Lets look at a very simple example of how you can import and use the websocket client in a piece of Rust code.

Simply importing the `nym_sdk` crate into your project allows you to create a client and send traffic through the mixnet.

```rust
use nym_sdk::mixnet;
use nym_sdk::mixnet::MixnetMessageSender;
 
#[tokio::main]
async fn main() {
    nym_bin_common::logging::setup_logging();
 
    // Passing no config makes the client fire up an ephemeral session and figure shit out on its own
    let mut client = mixnet::MixnetClient::connect_new().await.unwrap();
 
    // Be able to get our client address
    let our_address = client.nym_address();
    println!("Our client nym address is: {our_address}");
 
    // Send a message through the mixnet to ourselves
    client
        .send_plain_message(*our_address, "hello there")
        .await
        .unwrap();
 
    println!("Waiting for message (ctrl-c to exit)");
    client
        .on_messages(|msg| println!("Received: {}", String::from_utf8_lossy(&msg.message)))
        .await;
}
```


## Builder Patterns

Since there are two ways of creating an SDK client - ephemeral and with-storage - then there are two ways of applying the Builder Pattern to client creation.

## Mixnet Client Builder

You can spin up an ephemeral client like so. This client will not have a persistent identity and its keys will be dropped on restart. Since there is currently no way of reconnecting a client that has been disconnected after use, then treat disconnecting a client the same as dropping its keys entirely.

```rust
use nym_sdk::mixnet;
use nym_sdk::mixnet::MixnetMessageSender;
 
#[tokio::main]
async fn main() {
    nym_bin_common::logging::setup_logging();
 
    // Create client builder, including ephemeral keys. The builder can be usable in the context
    // where you don't want to connect just yet.
    let client = mixnet::MixnetClientBuilder::new_ephemeral()
        .build()
        .unwrap();
 
    // Now we connect to the mixnet, using ephemeral keys already created
    let mut client = client.connect_to_mixnet().await.unwrap();
 
    // Be able to get our client address
    let our_address = client.nym_address();
    println!("Our client nym address is: {our_address}");
 
    // Send a message through the mixnet to ourselves
    client
        .send_plain_message(*our_address, "hello there")
        .await
        .unwrap();
 
    println!("Waiting for message");
    if let Some(received) = client.wait_for_messages().await {
        for r in received {
            println!("Received: {}", String::from_utf8_lossy(&r.message));
        }
    }
 
    client.disconnect().await;
}
```

## Mixnet Client Builder with Storage

The previous example involves ephemeral keys - if we want to create and then maintain a client identity over time, our code becomes a little more complex as we need to create, store, and conditionally load these keys

```rust
use nym_sdk::mixnet;
use nym_sdk::mixnet::MixnetMessageSender;
use std::path::PathBuf;
 
#[tokio::main]
async fn main() {
    nym_bin_common::logging::setup_logging();
 
    // Specify some config options
    let config_dir = PathBuf::from("/tmp/mixnet-client");
    let storage_paths = mixnet::StoragePaths::new_from_dir(&config_dir).unwrap();
 
    // Create the client with a storage backend, and enable it by giving it some paths. If keys
    // exists at these paths, they will be loaded, otherwise they will be generated.
    let client = mixnet::MixnetClientBuilder::new_with_default_storage(storage_paths)
        .await
        .unwrap()
        .build()
        .unwrap();
 
    // Now we connect to the mixnet, using keys now stored in the paths provided.
    let mut client = client.connect_to_mixnet().await.unwrap();
 
    // Be able to get our client address
    let our_address = client.nym_address();
    println!("Our client nym address is: {our_address}");
 
    // Send a message throught the mixnet to ourselves
    client
        .send_plain_message(*our_address, "hello there")
        .await
        .unwrap();
 
    println!("Waiting for message");
    if let Some(received) = client.wait_for_messages().await {
        for r in received {
            println!("Received: {}", String::from_utf8_lossy(&r.message));
        }
    }
 
    client.disconnect().await;
}
```
As seen in the example above, the `mixnet::MixnetClientBuilder::new()` function handles checking for keys in a storage location, loading them if present, or creating them and storing them if not, making client key management very simple.

Assuming our client config is stored in `/tmp/mixnet-client`, the following files are generated:

```
$ tree /tmp/mixnet-client
mixnet-client
├── ack_key.pem
├── db.sqlite
├── db.sqlite-shm
├── db.sqlite-wal
├── gateway_details.json
├── gateway_shared.pem
├── persistent_reply_store.sqlite
├── private_encryption.pem
├── private_identity.pem
├── public_encryption.pem
└── public_identity.pem
1 directory, 11 files
```

## Send and Receive in Different Tasks

If you need to split the different actions of your client across different tasks, you can do so like this. You can think of this analogously to spliting a Tcp Stream into read/write. This functionality is also useful for embedding a sending and receiving client into different tasks.

```rust
use futures::StreamExt;
use nym_sdk::mixnet;
use nym_sdk::mixnet::MixnetMessageSender;
 
#[tokio::main]
async fn main() {
    nym_bin_common::logging::setup_logging();
 
    // Passing no config makes the client fire up an ephemeral session and figure stuff out on its own
    let mut client = mixnet::MixnetClient::connect_new().await.unwrap();
 
    // Be able to get our client address
    let our_address = *client.nym_address();
    println!("Our client nym address is: {our_address}");
 
    let sender = client.split_sender();
 
    // receiving task
    let receiving_task_handle = tokio::spawn(async move {
        if let Some(received) = client.next().await {
            println!("Received: {}", String::from_utf8_lossy(&received.message));
        }
 
        client.disconnect().await;
    });
 
    // sending task
    let sending_task_handle = tokio::spawn(async move {
        sender
            .send_plain_message(our_address, "hello from a different task!")
            .await
            .unwrap();
    });
 
    // wait for both tasks to be done
    println!("waiting for shutdown");
    sending_task_handle.await.unwrap();
    receiving_task_handle.await.unwrap();
}
```

## Anonymous Replies with SURBs (Single Use Reply Blocks)

Both functions used to send messages through the mixnet (`send_message` and `send_plain_message`) send a pre-determined number of SURBs along with their messages by default.

You can read more about how SURBs function under the hood [here](https://nym.com/docs/network/traffic/anonymous-replies).

In order to reply to an incoming message using SURBs, you can construct a `recipient` from the `sender_tag` sent along with the message you wish to reply to.

```rust
use nym_sdk::mixnet::{
    AnonymousSenderTag, MixnetClientBuilder, MixnetMessageSender, ReconstructedMessage,
    StoragePaths,
};
use std::path::PathBuf;
 
#[tokio::main]
async fn main() {
    nym_bin_common::logging::setup_logging();
 
    // Specify some config options
    let config_dir = PathBuf::from("/tmp/surb-example");
    let storage_paths = StoragePaths::new_from_dir(&config_dir).unwrap();
 
    // Create the client with a storage backend, and enable it by giving it some paths. If keys
    // exists at these paths, they will be loaded, otherwise they will be generated.
    let client = MixnetClientBuilder::new_with_default_storage(storage_paths)
        .await
        .unwrap()
        .build()
        .unwrap();
 
    // Now we connect to the mixnet, using keys now stored in the paths provided.
    let mut client = client.connect_to_mixnet().await.unwrap();
 
    // Be able to get our client address
    let our_address = client.nym_address();
    println!("\nOur client nym address is: {our_address}");
 
    // Send a message through the mixnet to ourselves using our nym address
    client
        .send_plain_message(*our_address, "hello there")
        .await
        .unwrap();
 
    // we're going to parse the sender_tag (AnonymousSenderTag) from the incoming message and use it to 'reply' to ourselves instead of our Nym address.
    // we know there will be a sender_tag since the sdk sends SURBs along with messages by default.
    println!("Waiting for message\n");
 
    // get the actual message - discard the empty vec sent along with a potential SURB topup request
    let mut message: Vec<ReconstructedMessage> = Vec::new();
    while let Some(new_message) = client.wait_for_messages().await {
        if new_message.is_empty() {
            continue;
        }
        message = new_message;
        break;
    }
 
    let mut parsed = String::new();
    if let Some(r) = message.first() {
        parsed = String::from_utf8(r.message.clone()).unwrap();
    }
    // parse sender_tag: we will use this to reply to sender without needing their Nym address
    let return_recipient: AnonymousSenderTag = message[0].sender_tag.unwrap();
    println!(
        "\nReceived the following message: {} \nfrom sender with surb bucket {}",
        parsed, return_recipient
    );
 
    // reply to self with it: note we use `send_str_reply` instead of `send_str`
    println!("Replying with using SURBs");
    client
        .send_reply(return_recipient, "hi an0n!")
        .await
        .unwrap();
 
    println!("Waiting for message (once you see it, ctrl-c to exit)\n");
    client
        .on_messages(|msg| println!("\nReceived: {}", String::from_utf8_lossy(&msg.message)))
        .await;
}
```


## Message Helpers
## Handling incoming messages
When listening out for a response to a sent message (e.g. if you have sent a request to a service, and are awaiting the response) you will want to await [non-empty messages (if you don't know why, read the info on this here)](https://nym.com/docs/developers/rust/mixnet/troubleshooting#client-receives-empty-messages-when-listening-for-response). This can be done with something like the helper functions here:
```rust
use nym_sdk::mixnet::ReconstructedMessage;
 
pub async fn wait_for_non_empty_message(
    client: &mut MixnetClient,
) -> anyhow::Result<ReconstructedMessage> {
    while let Some(mut new_message) = client.wait_for_messages().await {
        if !new_message.is_empty() {
            return Ok(new_message.pop().unwrap());
        }
    }
 
    bail!("did not receive any non-empty message")
}
 
pub fn handle_response(message: ReconstructedMessage) -> anyhow::Result<ResponseTypes> {
    ResponseTypes::try_deserialize(message.message)
}
 
// Note here that the only difference between handling a request and a response
// is that a request will have a sender_tag to parse.
//
// This is used for anonymous replies with SURBs.
pub fn handle_request(
    message: ReconstructedMessage,
) -> anyhow::Result<(RequestTypes, Option<AnonymousSenderTag>)> {
    let request = RequestTypes::try_deserialize(message.message)?;
    Ok((request, message.sender_tag))
}
```

The above helper functions are used as such by the client in tutorial example: it sends a message to the service (what the message is isn't important - just that your client has sent a message _somewhere_ and you are awaiting a response), waits for a _non_empty_ message, then handles it (then logs it - but you can do whatever you want, parse it, etc):

```rust
// Send serialised request to service via mixnet what is await-ed here is
// placing the message in the client's message queue, NOT the sending itself.
let _ = client
    .send_message(sp_address, message.serialize(), Default::default())
    .await;
 
// Await a non-empty message
let received = wait_for_non_empty_message(client).await?;
 
// Handle the response received (the non-empty message awaited above)
let sp_response = handle_response(received)?;
 
// Match JSON -> ResponseType
let res = match sp_response {
    crate::ResponseTypes::Balance(response) => {
        println!("{:#?}", response);
        response.balance
    }
};
```

## Iterating over incoming messages
It is recommended to use `nym_client.next().await` over `nym_client.wait_for_messages().await` as the latter will return one message at a time which will probably be easier to deal with. See the [parallel send and receive example](https://nym.com/docs/developers/rust/mixnet/examples/split-send) for an example.

## Remember to disconnect your client
You should always **manually disconnect your client** with `client.disconnect().await` as seen in the code examples. This is important as your client is writing to a local DB and dealing with SURB storage, so needs to gracefully shutdown.

# Message Types

There are several functions used to send outgoing messages through the Mixnet, each with a different level of customisation:

- `send(&self, message: InputMessage) -> Result<()>` Sends a `InputMessage` to the mixnet. This is the most low-level sending function, for full customization. Called by `send_message()`.
    
- `send_message<M>(&self, address: Recipient, message: M, surbs: IncludedSurbs) -> Result<()>` Sends bytes to the supplied Nym address. There is the option to specify the number of reply-SURBs to include. Called by `send_plain_message()`.
    
- `send_plain_message<M>(&self, address: Recipient, message: M) -> Result<()>` Sends data to the supplied Nym address with the default surb behaviour.
    

> Note we specify _outgoing_ messages above: this is because the SDK assumes that replies will be anonymous via [SURBs](https://nym.com/docs/network/traffic/anonymous-replies).

Replies rely on the creation of an `AnonymousSenderTag` by parsing and storing the `sender_tag` from incoming messages, and using this to reply, instead of the `Receipient` type used by the functions outlined above:

`send_reply<M>(&self, recipient_tag: AnonymousSenderTag, message: M) -> Result<()>` will send the reply message to the supplied anonymous recipient.

> You can find all of the function definitions [here(opens in a new tab)](https://github.com/nymtech/nym/blob/master/sdk/rust/nym-sdk/src/mixnet/traits.rs).


# Troubleshooting

Below are several common issues or questions you may have.

## Verbose `task client is being dropped` logging

### On client shutdown (expected)[

If this is happening at the end of your code when disconnecting your client, this is fine; we just have a verbose client! When calling `client.disconnect().await` this is simply informing you that the client is shutting down.

On client shutdown / disconnect this is to be expected - this can be seen in many of the code examples as well. We use the [`nym_bin_common::logging`(opens in a new tab)](https://github.com/nymtech/nym/blob/master/common/bin-common/src/logging/mod.rs) import to set logging in our example code. This defaults to `INFO` level.

If you wish to quickly lower the verbosity of your client process logs when developing you can prepend your command with `RUST_LOG=<LOGGING_LEVEL>`.

If you want to run the `builder.rs` example with only `WARN` level logging and below:

```
cargo run --example builder
```

Becomes:

```
RUST_LOG=warn cargo run --example builder
```

You can also make the logging _more_ verbose with:

```
RUST_LOG=debug cargo run --example builder
```

### Not on client shutdown (unexpected)[](https://nym.com/docs/developers/rust/mixnet/troubleshooting#not-on-client-shutdown-unexpected)

If this is happening unexpectedly then you might be shutting your client process down too early. See the [accidentally killing your client process](https://nym.com/docs/developers/rust/mixnet/troubleshooting#accidentally-killing-your-client-process-too-early) below for possible explanations and how to fix this issue.

## Accidentally killing your client process too early[](https://nym.com/docs/developers/rust/mixnet/troubleshooting#accidentally-killing-your-client-process-too-early)

If you are seeing either of the following errors when trying to run a client, specifically sending a message, then you may be accidentally killing your client process.

```
 2023-11-02T10:31:03.930Z INFO  TaskClient-BaseNymClient-real_traffic_controller-ack_control-action_controller                           > the task client is getting dropped 2023-11-02T10:31:04.625Z INFO  TaskClient-BaseNymClient-received_messages_buffer-request_receiver                                       > the task client is getting dropped 2023-11-02T10:31:04.626Z DEBUG nym_client_core::client::real_messages_control::acknowledgement_control::input_message_listener          > InputMessageListener: Exiting 2023-11-02T10:31:04.626Z INFO  TaskClient-BaseNymClient-real_traffic_controller-ack_control-input_message_listener                      > the task client is getting dropped 2023-11-02T10:31:04.626Z INFO  TaskClient-BaseNymClient-real_traffic_controller-reply_control                                           > the task client is getting dropped 2023-11-02T10:31:04.626Z DEBUG nym_client_core::client::real_messages_control                                                           > The reply controller has finished execution! 2023-11-02T10:31:04.626Z DEBUG nym_client_core::client::real_messages_control::acknowledgement_control                                  > The input listener has finished execution! 2023-11-02T10:31:04.626Z INFO  nym_task::manager                                                                                        > All registered tasks succesfully shutdown
```

```
 2023-11-02T11:22:08.408Z ERROR TaskClient-BaseNymClient-topology_refresher                                                  > Assuming this means we should shutdown... 2023-11-02T11:22:08.408Z ERROR TaskClient-BaseNymClient-mix_traffic_controller                                              > Polling shutdown failed: channel closed 2023-11-02T11:22:08.408Z INFO  TaskClient-BaseNymClient-gateway_transceiver-child                                           > the task client is getting dropped 2023-11-02T11:22:08.408Z ERROR TaskClient-BaseNymClient-mix_traffic_controller                                              > Assuming this means we should shutdown...thread 'tokio-runtime-worker' panicked at 'action control task has died: TrySendError { kind: Disconnected }', /home/.local/share/cargo/git/checkouts/nym-fbd2f6ea2e760da9/a800cba/common/client-core/src/client/real_messages_control/message_handler.rs:634:14note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace 2023-11-02T11:22:08.477Z INFO  TaskClient-BaseNymClient-real_traffic_controller-ack_control-input_message_listener          > the task client is getting dropped 2023-11-02T11:22:08.477Z ERROR TaskClient-BaseNymClient-real_traffic_controller-ack_control-input_message_listener          > Polling shutdown failed: channel closed 2023-11-02T11:22:08.477Z ERROR TaskClient-BaseNymClient-real_traffic_controller-ack_control-input_message_listener          > Assuming this means we should shutdown...
```

Using the following piece of code as an example:

```rust
use nym_sdk::mixnet::{MixnetClient, MixnetMessageSender, Recipient};
use clap::Parser;
 
#[derive(Debug, Clone, Parser)]
enum Opts {
    Client {
        recipient: Recipient
    }
}
 
#[tokio::main]
async fn main() {
    let opts: Opts = Parser::parse();
    nym_bin_common::logging::setup_logging();
 
    let mut nym_client = MixnetClient::connect_new().await.expect("Could not build Nym client");
 
    match opts {
        Opts::Client { recipient } => {
            nym_client.send_plain_message(recipient, "some message string").await.expect("send failed");
        }
    }
}
```

This is a simplified snippet of code for sending a simple hardcoded message with the following command:

```
cargo run client <RECIPIENT_NYM_ADDRESS>
```

You might assume that `send`-ing your message would _just work_ as `nym_client.send_plain_message()` is an async function; you might expect that the client will block until the message is actually sent into the mixnet, then shutdown.

However, this is not true.

**This will only block until the message is put into client's internal queue**. Therefore in the above example, the client is being shut down before the message is _actually sent to the mixnet_; after being placed in the client's internal queue, there is still work to be done under the hood, such as route encrypting the message and placing it amongst the stream of cover traffic.

The simple solution? Make sure the program/client stays active, either by calling `sleep`, or listening out for new messages. As sending a one-shot message without listening out for a response is likely not what you'll be doing, then you will be then awaiting a response (see the [message helpers page](https://nym.com/docs/developers/rust/mixnet/message-helpers) for an example of this).

Furthermore, you should always **manually disconnect your client** with `client.disconnect().await` as seen in the code examples. This is important as your client is writing to a local DB and dealing with SURB storage.

## Client receives empty messages when listening for response[](https://nym.com/docs/developers/rust/mixnet/troubleshooting#client-receives-empty-messages-when-listening-for-response)

If you are sending out a message, it makes sense for your client to then listen out for incoming messages; this would probably be the reply you get from the service you've sent a message to.

You might however be receiving messages without data attached to them / empty payloads. This is most likely because your client is receiving a message containing a [SURB request](https://nym.com/docs/network/traffic/anonymous-replies) - a SURB requesting more SURB packets to be sent to the service, in order for them to have enough packets (with a big enough overall payload) to split the entire response to your initial request across.

Whether the `data` of a SURB request being empty is a feature or a bug is to be decided - there is some discussion surrounding whether we can use SURB requests to send additional data to streamline the process of sending large replies across the mixnet.

You can find a few helper functions [here](https://nym.com/docs/developers/rust/mixnet/message-helpers) to help deal with this issue in the meantime.

> If you can think of a more succinct or different way of handling this do reach out - we're happy to hear other opinions

## Lots of `duplicate fragment received` messages[](https://nym.com/docs/developers/rust/mixnet/troubleshooting#lots-of-duplicate-fragment-received-messages)

You might see a lot of `WARN` level logs about duplicate fragments in your logs, depending on the log level you're using. This occurs when a packet is retransmitted somewhere in the Mixnet, but then the original makes it to the destination client as well. This is not something to do with your client logic, but instead the state of the Mixnet.


# Source Code

client.rs
```rust
// Copyright 2022-2023 - Nym Technologies SA <contact@nymtech.net>
// SPDX-License-Identifier: Apache-2.0

use super::{connection_state::BuilderState, Config, StoragePaths};
use crate::bandwidth::BandwidthAcquireClient;
use crate::mixnet::socks5_client::Socks5MixnetClient;
use crate::mixnet::{CredentialStorage, MixnetClient, Recipient};
use crate::GatewayTransceiver;
use crate::NymNetworkDetails;
use crate::{Error, Result};
use futures::channel::mpsc;
use futures::StreamExt;
use log::{debug, warn};
use nym_client_core::client::base_client::storage::helpers::{
    get_active_gateway_identity, get_all_registered_identities, has_gateway_details,
    set_active_gateway,
};
use nym_client_core::client::base_client::storage::{
    Ephemeral, GatewaysDetailsStore, MixnetClientStorage, OnDiskPersistent,
};
use nym_client_core::client::base_client::BaseClient;
use nym_client_core::client::key_manager::persistence::KeyStore;
use nym_client_core::client::{
    base_client::BaseClientBuilder, replies::reply_storage::ReplyStorageBackend,
};
use nym_client_core::config::{DebugConfig, ForgetMe, StatsReporting};
use nym_client_core::error::ClientCoreError;
use nym_client_core::init::helpers::gateways_for_init;
use nym_client_core::init::setup_gateway;
use nym_client_core::init::types::{GatewaySelectionSpecification, GatewaySetup};
use nym_credentials_interface::TicketType;
use nym_crypto::hkdf::DerivationMaterial;
use nym_socks5_client_core::config::Socks5;
use nym_task::{TaskClient, TaskHandle, TaskStatus};
use nym_topology::provider_trait::TopologyProvider;
use nym_validator_client::{nyxd, QueryHttpRpcNyxdClient, UserAgent};
use rand::rngs::OsRng;
use std::path::Path;
use std::path::PathBuf;
#[cfg(unix)]
use std::sync::Arc;
use url::Url;
use zeroize::Zeroizing;

// The number of surbs to include in a message by default
const DEFAULT_NUMBER_OF_SURBS: u32 = 10;

#[derive(Default)]
pub struct MixnetClientBuilder<S: MixnetClientStorage = Ephemeral> {
    config: Config,
    storage_paths: Option<StoragePaths>,
    socks5_config: Option<Socks5>,

    wait_for_gateway: bool,
    custom_topology_provider: Option<Box<dyn TopologyProvider + Send + Sync>>,
    custom_gateway_transceiver: Option<Box<dyn GatewayTransceiver + Send + Sync>>,
    custom_shutdown: Option<TaskClient>,
    force_tls: bool,
    user_agent: Option<UserAgent>,
    #[cfg(unix)]
    connection_fd_callback: Option<Arc<dyn Fn(std::os::fd::RawFd) + Send + Sync>>,

    // TODO: incorporate it properly into `MixnetClientStorage` (I will need it in wasm anyway)
    gateway_endpoint_config_path: Option<PathBuf>,

    storage: S,
    forget_me: ForgetMe,
    derivation_material: Option<DerivationMaterial>,
}

impl MixnetClientBuilder<Ephemeral> {
    /// Creates a client builder with ephemeral storage.
    #[must_use]
    pub fn new_ephemeral() -> Self {
        MixnetClientBuilder {
            ..Default::default()
        }
    }

    /// Create a client builder with default values.
    #[must_use]
    pub fn new() -> Self {
        Self::new_ephemeral()
    }
}

impl MixnetClientBuilder<OnDiskPersistent> {
    pub async fn new_with_default_storage(storage_paths: StoragePaths) -> Result<Self> {
        Ok(MixnetClientBuilder {
            config: Default::default(),
            storage_paths: None,
            socks5_config: None,
            wait_for_gateway: false,
            custom_topology_provider: None,
            storage: storage_paths
                .initialise_default_persistent_storage()
                .await?,
            gateway_endpoint_config_path: None,
            custom_shutdown: None,
            custom_gateway_transceiver: None,
            force_tls: false,
            user_agent: None,
            #[cfg(unix)]
            connection_fd_callback: None,
            forget_me: Default::default(),
            derivation_material: None,
        })
    }
}

impl<S> MixnetClientBuilder<S>
where
    S: MixnetClientStorage + Clone + 'static,
    S::ReplyStore: Send + Sync,
    S::GatewaysDetailsStore: Sync,
    <S::ReplyStore as ReplyStorageBackend>::StorageError: Sync + Send,
    <S::CredentialStore as CredentialStorage>::StorageError: Send + Sync,
    <S::KeyStore as KeyStore>::StorageError: Send + Sync,
    <S::GatewaysDetailsStore as GatewaysDetailsStore>::StorageError: Send + Sync,
{
    /// Creates a client builder with the provided client storage implementation.
    #[must_use]
    pub fn new_with_storage(storage: S) -> MixnetClientBuilder<S> {
        MixnetClientBuilder {
            config: Default::default(),
            storage_paths: None,
            socks5_config: None,
            wait_for_gateway: false,
            custom_topology_provider: None,
            custom_gateway_transceiver: None,
            custom_shutdown: None,
            force_tls: false,
            user_agent: None,
            #[cfg(unix)]
            connection_fd_callback: None,
            gateway_endpoint_config_path: None,
            storage,
            forget_me: Default::default(),
            derivation_material: None,
        }
    }

    /// Change the underlying storage implementation.
    #[must_use]
    pub fn set_storage<T: MixnetClientStorage>(self, storage: T) -> MixnetClientBuilder<T> {
        MixnetClientBuilder {
            config: self.config,
            storage_paths: self.storage_paths,
            socks5_config: self.socks5_config,
            wait_for_gateway: self.wait_for_gateway,
            custom_topology_provider: self.custom_topology_provider,
            custom_gateway_transceiver: self.custom_gateway_transceiver,
            custom_shutdown: self.custom_shutdown,
            force_tls: self.force_tls,
            user_agent: self.user_agent,
            #[cfg(unix)]
            connection_fd_callback: self.connection_fd_callback,
            gateway_endpoint_config_path: self.gateway_endpoint_config_path,
            storage,
            forget_me: self.forget_me,
            derivation_material: self.derivation_material,
        }
    }

    #[must_use]
    pub fn with_derivation_material(mut self, derivation_material: DerivationMaterial) -> Self {
        self.derivation_material = Some(derivation_material);
        self
    }

    /// Change the underlying storage of this builder to use default implementation of on-disk disk_persistence.
    #[must_use]
    pub fn set_default_storage(
        self,
        storage: OnDiskPersistent,
    ) -> MixnetClientBuilder<OnDiskPersistent> {
        self.set_storage(storage)
    }

    #[must_use]
    pub fn with_forget_me(mut self, forget_me: ForgetMe) -> Self {
        self.forget_me = forget_me;
        self
    }

    /// Request a specific gateway instead of a random one.
    #[must_use]
    pub fn request_gateway(mut self, user_chosen_gateway: String) -> Self {
        self.config.user_chosen_gateway = Some(user_chosen_gateway);
        self
    }

    #[must_use]
    pub fn with_extended_topology(mut self, use_extended_topology: bool) -> Self {
        self.config.debug_config.topology.use_extended_topology = use_extended_topology;
        self
    }

    #[must_use]
    pub fn with_ignore_epoch_roles(mut self, ignore_epoch_roles: bool) -> Self {
        self.config.debug_config.topology.ignore_egress_epoch_role = ignore_epoch_roles;
        self
    }

    /// Use a specific network instead of the default (mainnet) one.
    #[must_use]
    pub fn network_details(mut self, network_details: NymNetworkDetails) -> Self {
        self.config.network_details = network_details;
        self
    }

    /// Attempt to only choose a gateway that supports wss protocol.
    #[must_use]
    pub fn force_tls(mut self, must_use_tls: bool) -> Self {
        self.force_tls = must_use_tls;
        self
    }

    /// Enable paid coconut bandwidth credentials mode.
    #[must_use]
    pub fn enable_credentials_mode(mut self) -> Self {
        self.config.enabled_credentials_mode = true;
        self
    }

    /// Enable paid coconut bandwidth credentials mode.
    #[must_use]
    pub fn credentials_mode(mut self, credentials_mode: bool) -> Self {
        self.config.enabled_credentials_mode = credentials_mode;
        self
    }

    /// Use a custom debugging configuration.
    #[must_use]
    pub fn debug_config(mut self, debug_config: DebugConfig) -> Self {
        self.config.debug_config = debug_config;
        self
    }

    /// Configure the SOCKS5 mode.
    #[must_use]
    pub fn socks5_config(mut self, socks5_config: Socks5) -> Self {
        self.socks5_config = Some(socks5_config);
        self
    }

    /// Use a custom topology provider.
    #[must_use]
    pub fn custom_topology_provider(
        mut self,
        topology_provider: Box<dyn TopologyProvider + Send + Sync>,
    ) -> Self {
        self.custom_topology_provider = Some(topology_provider);
        self
    }

    /// Use an externally managed shutdown mechanism.
    #[must_use]
    pub fn custom_shutdown(mut self, shutdown: TaskClient) -> Self {
        self.custom_shutdown = Some(shutdown);
        self
    }

    /// Attempt to wait for the selected gateway (if applicable) to come online if its currently not bonded.
    #[must_use]
    pub fn with_wait_for_gateway(mut self, wait_for_gateway: bool) -> Self {
        self.wait_for_gateway = wait_for_gateway;
        self
    }

    #[must_use]
    pub fn with_user_agent(mut self, user_agent: UserAgent) -> Self {
        self.user_agent = Some(user_agent);
        self
    }

    #[must_use]
    pub fn with_statistics_reporting(mut self, config: StatsReporting) -> Self {
        self.config.debug_config.stats_reporting = config;
        self
    }

    #[cfg(unix)]
    #[must_use]
    pub fn with_connection_fd_callback(
        mut self,
        connection_fd_callback: Arc<dyn Fn(std::os::fd::RawFd) + Send + Sync>,
    ) -> Self {
        self.connection_fd_callback = Some(connection_fd_callback);
        self
    }

    /// Use custom mixnet sender that might not be the default websocket gateway connection.
    /// only for advanced use
    #[must_use]
    pub fn custom_gateway_transceiver(
        mut self,
        gateway_transceiver: Box<dyn GatewayTransceiver + Send + Sync>,
    ) -> Self {
        self.custom_gateway_transceiver = Some(gateway_transceiver);
        self
    }

    /// Use specified file for storing gateway configuration.
    pub fn gateway_endpoint_config_path<P: AsRef<Path>>(mut self, path: P) -> Self {
        self.gateway_endpoint_config_path = Some(path.as_ref().to_owned());
        self
    }

    /// Construct a [`DisconnectedMixnetClient`] from the setup specified.
    pub fn build(self) -> Result<DisconnectedMixnetClient<S>> {
        let mut client =
            DisconnectedMixnetClient::new(self.config, self.socks5_config, self.storage)?;

        client.custom_gateway_transceiver = self.custom_gateway_transceiver;
        client.custom_topology_provider = self.custom_topology_provider;
        client.custom_shutdown = self.custom_shutdown;
        client.wait_for_gateway = self.wait_for_gateway;
        client.force_tls = self.force_tls;
        client.user_agent = self.user_agent;
        #[cfg(unix)]
        if self.connection_fd_callback.is_some() {
            client.connection_fd_callback = self.connection_fd_callback;
        }
        client.forget_me = self.forget_me;
        client.derivation_material = self.derivation_material;
        Ok(client)
    }
}

/// Represents a client that is not yet connected to the mixnet.
///
/// Represents a client that is not yet connected to the mixnet. You typically create one when you
/// want to have a separate configuration and connection phase. Once the mixnet client builder is
/// configured, call [`MixnetClientBuilder::connect_to_mixnet()`] or
/// [`MixnetClientBuilder::connect_to_mixnet_via_socks5()`] to transition to a connected
/// client.
pub struct DisconnectedMixnetClient<S>
where
    S: MixnetClientStorage + Clone,
{
    /// Client configuration
    config: Config,

    /// Socks5 configuration
    socks5_config: Option<Socks5>,

    /// The client can be in one of multiple states, depending on how it is created and if it's
    /// connected to the mixnet.
    state: BuilderState,

    /// Underlying storage of this client.
    storage: S,

    /// In the case of enabled credentials, a client instance responsible for querying the state of the
    /// dkg and coconut contracts
    dkg_query_client: Option<QueryHttpRpcNyxdClient>,

    /// Alternative provider of network topology used for constructing sphinx packets.
    custom_topology_provider: Option<Box<dyn TopologyProvider + Send + Sync>>,

    /// advanced usage of custom gateways
    custom_gateway_transceiver: Option<Box<dyn GatewayTransceiver + Send + Sync>>,

    /// Attempt to wait for the selected gateway (if applicable) to come online if its currently not bonded.
    wait_for_gateway: bool,

    /// Force the client to connect using wss protocol with the gateway.
    force_tls: bool,

    /// Allows passing an externally controlled shutdown handle.
    custom_shutdown: Option<TaskClient>,

    user_agent: Option<UserAgent>,

    /// Callback on the websocket fd as soon as the connection has been established
    #[cfg(unix)]
    connection_fd_callback: Option<Arc<dyn Fn(std::os::fd::RawFd) + Send + Sync>>,

    forget_me: ForgetMe,

    /// The derivation material to use for the client keys, its up to the caller to save this for rederivation later
    derivation_material: Option<DerivationMaterial>,
}

impl<S> DisconnectedMixnetClient<S>
where
    S: MixnetClientStorage + Clone + 'static,
    S::ReplyStore: Send + Sync,
    S::GatewaysDetailsStore: Sync,
    <S::ReplyStore as ReplyStorageBackend>::StorageError: Sync + Send,
    <S::CredentialStore as CredentialStorage>::StorageError: Send + Sync,
    <S::KeyStore as KeyStore>::StorageError: Send + Sync,
    <S::GatewaysDetailsStore as GatewaysDetailsStore>::StorageError: Send + Sync,
{
    /// Create a new mixnet client in a disconnected state. The default configuration,
    /// creates a new mainnet client with ephemeral keys stored in RAM, which will be discarded at
    /// application close.
    ///
    /// Callers have the option of supplying further parameters to:
    /// - store persistent identities at a location on-disk, if desired;
    /// - use SOCKS5 mode
    fn new(
        config: Config,
        socks5_config: Option<Socks5>,
        storage: S,
    ) -> Result<DisconnectedMixnetClient<S>> {
        // don't create dkg client for the bandwidth controller if credentials are disabled
        let dkg_query_client = if config.enabled_credentials_mode {
            let client_config =
                nyxd::Config::try_from_nym_network_details(&config.network_details)?;
            let client = QueryHttpRpcNyxdClient::connect(
                client_config,
                config.network_details.endpoints[0].nyxd_url.as_str(),
            )?;
            Some(client)
        } else {
            None
        };

        let forget_me = config.debug_config.forget_me;

        Ok(DisconnectedMixnetClient {
            config,
            socks5_config,
            state: BuilderState::New,
            dkg_query_client,
            storage,
            custom_topology_provider: None,
            custom_gateway_transceiver: None,
            wait_for_gateway: false,
            force_tls: false,
            custom_shutdown: None,
            user_agent: None,
            #[cfg(unix)]
            connection_fd_callback: None,
            forget_me,
            derivation_material: None,
        })
    }

    fn get_api_endpoints(&self) -> Vec<Url> {
        self.config
            .network_details
            .endpoints
            .iter()
            .filter_map(|details| details.api_url.as_ref())
            .filter_map(|s| Url::parse(s).ok())
            .collect()
    }

    fn get_nyxd_endpoints(&self) -> Vec<Url> {
        self.config
            .network_details
            .endpoints
            .iter()
            .map(|details| details.nyxd_url.as_ref())
            .filter_map(|s| Url::parse(s).ok())
            .collect()
    }

    async fn setup_client_keys(&self) -> Result<()> {
        let mut rng = OsRng;
        let key_store = self.storage.key_store();

        if key_store.load_keys().await.is_err() {
            debug!("Generating new client keys");
            nym_client_core::init::generate_new_client_keys(&mut rng, key_store).await?;
        }

        Ok(())
    }

    async fn print_all_registered_gateway_identities(&self) {
        match get_all_registered_identities(self.storage.gateway_details_store()).await {
            Err(err) => {
                warn!("failed to query for all registered gateways: {err}")
            }
            Ok(all_ids) => {
                if !all_ids.is_empty() {
                    debug!("this client is already registered with the following gateways:");
                    for id in all_ids {
                        debug!("{id}")
                    }
                }
            }
        }
    }

    async fn print_selected_gateway(&self) {
        match self.storage.gateway_details_store().active_gateway().await {
            Err(err) => {
                warn!("failed to query for the current active gateway: {err}")
            }
            Ok(active) => {
                if let Some(active) = active.registration {
                    let id = active.details.gateway_id();
                    debug!("currently selected gateway: {0}", id);
                }
            }
        }
    }

    async fn set_active_gateway_if_previously_registered(
        &self,
        user_chosen_gateway: &str,
    ) -> Result<bool> {
        let storage = self.storage.gateway_details_store();
        // Strictly speaking, `set_active_gateway` does this check internally as well, but since the
        // error is boxed away and we're using a generic storage, it's not so easy to match on it.
        // This function is at least less likely to fail on something unrelated to the existence of
        // the gateway in the set of registered gateways
        if has_gateway_details(storage, user_chosen_gateway).await? {
            set_active_gateway(storage, user_chosen_gateway).await?;
            Ok(true)
        } else {
            Ok(false)
        }
    }

    async fn new_gateway_setup(&self) -> Result<GatewaySetup, ClientCoreError> {
        let nym_api_endpoints = self.get_api_endpoints();

        let selection_spec = GatewaySelectionSpecification::new(
            self.config.user_chosen_gateway.clone(),
            None,
            self.force_tls,
        );

        let user_agent = self.user_agent.clone();

        let topology_cfg = &self.config.debug_config.topology;
        let mut rng = OsRng;
        let available_gateways = gateways_for_init(
            &mut rng,
            &nym_api_endpoints,
            user_agent,
            topology_cfg.minimum_gateway_performance,
            topology_cfg.ignore_ingress_epoch_role,
        )
        .await?;

        Ok(GatewaySetup::New {
            specification: selection_spec,
            available_gateways,
        })
    }

    /// Register with a gateway. If a gateway is provided in the config then that will try to be
    /// used. If none is specified, a gateway at random will be picked. The used gateway is saved
    /// as the active gateway.
    ///
    /// # Errors
    ///
    /// This function will return an error if you try to re-register when in an already registered
    /// state.
    pub async fn setup_gateway(&mut self) -> Result<()> {
        if !matches!(self.state, BuilderState::New) {
            return Err(Error::ReregisteringGatewayNotSupported);
        }

        self.print_all_registered_gateway_identities().await;
        self.print_selected_gateway().await;

        // Try to set active gateway to the same as the user chosen one, if it's in the set of
        // gateways that is already registered.
        if let Some(ref user_chosen_gateway) = self.config.user_chosen_gateway {
            if self
                .set_active_gateway_if_previously_registered(user_chosen_gateway)
                .await?
            {
                debug!("user chosen gateway is already registered, set as active");
            }
        }

        let active_gateway =
            get_active_gateway_identity(self.storage.gateway_details_store()).await?;

        // Determine the gateway setup based on the currently active gateway and the user-chosen
        // gateway.
        let gateway_setup = match (self.config.user_chosen_gateway.as_ref(), active_gateway) {
            // When a user-chosen gateway exists and matches the active one.
            (Some(user_chosen_gateway), Some(active_gateway))
                if &active_gateway.to_base58_string() == user_chosen_gateway =>
            {
                GatewaySetup::MustLoad { gateway_id: None }
            }
            // When a user-chosen gateway exists but there's no active gateway, or it doesn't match the active one.
            (Some(_), _) => self.new_gateway_setup().await?,
            // When no user-chosen gateway exists but there's an active gateway.
            (None, Some(_)) => GatewaySetup::MustLoad { gateway_id: None },
            // When there's no user-chosen gateway and no active gateway.
            (None, None) => self.new_gateway_setup().await?,
        };

        // this will perform necessary key and details load and optional store
        let init_results = setup_gateway(
            gateway_setup,
            self.storage.key_store(),
            self.storage.gateway_details_store(),
        )
        .await?;

        set_active_gateway(
            self.storage.gateway_details_store(),
            &init_results.gateway_id().to_base58_string(),
        )
        .await?;

        self.state = BuilderState::Registered {};
        Ok(())
    }

    /// Creates an associated [`BandwidthAcquireClient`] that can be used to acquire bandwidth
    /// credentials of particular type for this client to consume.
    pub async fn create_bandwidth_client(
        &self,
        mnemonic: String,
        ticketbook_type: TicketType,
    ) -> Result<BandwidthAcquireClient<S::CredentialStore>> {
        if !self.config.enabled_credentials_mode {
            return Err(Error::DisabledCredentialsMode);
        }
        let client_id_array = Zeroizing::new(
            self.storage
                .key_store()
                .load_keys()
                .await
                .map_err(|e| Error::KeyStorageError {
                    source: Box::new(e),
                })?
                .identity_keypair()
                .private_key()
                .to_bytes(),
        );
        let client_id = client_id_array.to_vec();

        BandwidthAcquireClient::new(
            self.config.network_details.clone(),
            mnemonic,
            self.storage.credential_store().clone(),
            client_id,
            ticketbook_type,
        )
    }

    async fn connect_to_mixnet_common(mut self) -> Result<(BaseClient, Recipient)> {
        self.setup_client_keys().await?;
        self.setup_gateway().await?;

        let nyxd_endpoints = self.get_nyxd_endpoints();
        let nym_api_endpoints = self.get_api_endpoints();

        // a temporary workaround
        let base_config = self
            .config
            .as_base_client_config(nyxd_endpoints, nym_api_endpoints.clone());

        let mut base_builder: BaseClientBuilder<_, _> =
            BaseClientBuilder::new(base_config, self.storage, self.dkg_query_client)
                .with_wait_for_gateway(self.wait_for_gateway)
                .with_forget_me(&self.forget_me)
                .with_derivation_material(self.derivation_material);

        if let Some(user_agent) = self.user_agent {
            base_builder = base_builder.with_user_agent(user_agent);
        }

        if let Some(topology_provider) = self.custom_topology_provider {
            base_builder = base_builder.with_topology_provider(topology_provider);
        }

        if let Some(custom_shutdown) = self.custom_shutdown {
            base_builder = base_builder.with_shutdown(custom_shutdown)
        }

        if let Some(gateway_transceiver) = self.custom_gateway_transceiver {
            base_builder = base_builder.with_gateway_transceiver(gateway_transceiver);
        }

        #[cfg(unix)]
        if let Some(connection_fd_callback) = self.connection_fd_callback {
            base_builder = base_builder.with_connection_fd_callback(connection_fd_callback);
        }

        let started_client = base_builder.start_base().await?;
        self.state = BuilderState::Registered {};
        let nym_address = started_client.address;

        Ok((started_client, nym_address))
    }

    /// Connect the client to the mixnet via SOCKS5. A SOCKS5 configuration must be specified
    /// before attempting to connect.
    ///
    /// - If the client is already registered with a gateway, use that gateway.
    /// - If no gateway is registered, but there is an existing configuration and key, use that.
    /// - If no gateway is registered, and there is no pre-existing configuration or key, try to
    ///   register a new gateway.
    ///
    /// # Example
    ///
    /// ```no_run
    /// use nym_sdk::mixnet;
    ///
    /// #[tokio::main]
    /// async fn main() {
    ///     let receiving_client = mixnet::MixnetClient::connect_new().await.unwrap();
    ///     let socks5_config = mixnet::Socks5::new(receiving_client.nym_address().to_string());
    ///     let client = mixnet::MixnetClientBuilder::new_ephemeral()
    ///         .socks5_config(socks5_config)
    ///         .build()
    ///         .unwrap();
    ///     let client = client.connect_to_mixnet_via_socks5().await.unwrap();
    /// }
    /// ```
    pub async fn connect_to_mixnet_via_socks5(self) -> Result<Socks5MixnetClient> {
        let socks5_config = self
            .socks5_config
            .clone()
            .ok_or(Error::Socks5Config { set: false })?;
        let debug_config = self.config.debug_config;
        let packet_type = self.config.debug_config.traffic.packet_type;
        let (mut started_client, nym_address) = self.connect_to_mixnet_common().await?;
        let (socks5_status_tx, mut socks5_status_rx) = mpsc::channel(128);

        let client_input = started_client.client_input.register_producer();
        let client_output = started_client.client_output.register_consumer();
        let client_state = started_client.client_state;

        nym_socks5_client_core::NymClient::<S>::start_socks5_listener(
            &socks5_config,
            debug_config,
            client_input,
            client_output,
            client_state.clone(),
            nym_address,
            started_client.task_handle.get_handle(),
            packet_type,
        );

        // TODO: more graceful handling here, surely both variants should work... I think?
        if let TaskHandle::Internal(task_manager) = &mut started_client.task_handle {
            task_manager
                .start_status_listener(socks5_status_tx, TaskStatus::Ready)
                .await;
            match socks5_status_rx
                .next()
                .await
                .ok_or(Error::Socks5NotStarted)?
                .as_any()
                .downcast_ref::<TaskStatus>()
                .ok_or(Error::Socks5NotStarted)?
            {
                TaskStatus::Ready => {
                    log::debug!("Socks5 connected");
                }
                TaskStatus::ReadyWithGateway(gateway) => {
                    log::debug!("Socks5 connected to {gateway}");
                }
            }
        } else {
            return Err(Error::new_unsupported(
                "connecting with socks5 is currently unsupported with custom shutdown",
            ));
        }

        Ok(Socks5MixnetClient {
            nym_address,
            client_state,
            task_handle: started_client.task_handle,
            socks5_config,
        })
    }

    /// Connect the client to the mixnet.
    ///
    /// - If the client is already registered with a gateway, use that gateway.
    /// - If no gateway is registered, but there is an existing configuration and key, use that.
    /// - If no gateway is registered, and there is no pre-existing configuration or key, try to
    ///   register a new gateway.
    ///
    /// # Example
    ///
    /// ```no_run
    /// use nym_sdk::mixnet;
    ///
    /// #[tokio::main]
    /// async fn main() {
    ///     let client = mixnet::MixnetClientBuilder::new_ephemeral()
    ///         .build()
    ///         .unwrap();
    ///     let client = client.connect_to_mixnet().await.unwrap();
    /// }
    /// ```
    pub async fn connect_to_mixnet(self) -> Result<MixnetClient> {
        if self.socks5_config.is_some() {
            return Err(Error::Socks5Config { set: true });
        }
        let (mut started_client, nym_address) = self.connect_to_mixnet_common().await?;
        let client_input = started_client.client_input.register_producer();
        let mut client_output = started_client.client_output.register_consumer();
        let client_state: nym_client_core::client::base_client::ClientState =
            started_client.client_state;
        let stats_events_reporter = started_client.stats_reporter;

        let identity_keys = started_client.identity_keys.clone();
        let reconstructed_receiver = client_output.register_receiver()?;

        Ok(MixnetClient::new(
            nym_address,
            identity_keys,
            client_input,
            client_output,
            client_state,
            reconstructed_receiver,
            stats_events_reporter,
            started_client.task_handle,
            None,
            started_client.client_request_sender,
            started_client.forget_me,
        ))
    }
}

pub enum IncludedSurbs {
    Amount(u32),
    ExposeSelfAddress,
}
impl Default for IncludedSurbs {
    fn default() -> Self {
        Self::Amount(DEFAULT_NUMBER_OF_SURBS)
    }
}

impl IncludedSurbs {
    pub fn new(reply_surbs: u32) -> Self {
        Self::Amount(reply_surbs)
    }

    pub fn none() -> Self {
        Self::Amount(0)
    }

    pub fn expose_self_address() -> Self {
        Self::ExposeSelfAddress
    }
}
```

config.rs
```rust
use nym_client_core::config::{Client as ClientConfig, DebugConfig};
use nym_network_defaults::NymNetworkDetails;
use nym_socks5_client_core::config::BaseClientConfig;
use url::Url;

const DEFAULT_SDK_CLIENT_ID: &str = "_default-nym-sdk-client";

/// Config struct for [`crate::mixnet::MixnetClient`]
#[derive(Default)]
pub struct Config {
    /// If the user has explicitly specified a gateway.
    pub user_chosen_gateway: Option<String>,

    /// The details of the network we're using. It defaults to the mainnet network.
    pub network_details: NymNetworkDetails,

    /// Whether to attempt to use gateway with bandwidth credential requirement.
    pub enabled_credentials_mode: bool,

    /// Flags controlling all sorts of internal client behaviour.
    /// Changing these risk compromising network anonymity!
    pub debug_config: DebugConfig,
}

impl Config {
    // I really dislike this workaround.
    pub fn as_base_client_config(
        &self,
        nyxd_endpoints: Vec<Url>,
        nym_api_endpoints: Vec<Url>,
    ) -> BaseClientConfig {
        BaseClientConfig::from_client_config(
            ClientConfig::new(
                DEFAULT_SDK_CLIENT_ID,
                env!("CARGO_PKG_VERSION"),
                !self.enabled_credentials_mode,
                nyxd_endpoints,
                nym_api_endpoints,
            ),
            self.debug_config,
        )
    }
}
```

native_client.rs
```rust
use crate::mixnet::client::MixnetClientBuilder;
use crate::mixnet::traits::MixnetMessageSender;
use crate::{Error, Result};
use async_trait::async_trait;
use futures::{ready, Stream, StreamExt};
use log::{debug, error};
use nym_client_core::client::base_client::GatewayConnection;
use nym_client_core::client::mix_traffic::ClientRequestSender;
use nym_client_core::client::{
    base_client::{ClientInput, ClientOutput, ClientState},
    inbound_messages::InputMessage,
    received_buffer::ReconstructedMessagesReceiver,
};
use nym_client_core::config::ForgetMe;
use nym_crypto::asymmetric::ed25519;
use nym_gateway_requests::ClientRequest;
use nym_sphinx::addressing::clients::Recipient;
use nym_sphinx::{params::PacketType, receiver::ReconstructedMessage};
use nym_statistics_common::clients::{ClientStatsEvents, ClientStatsSender};
use nym_task::{
    connections::{ConnectionCommandSender, LaneQueueLengths},
    TaskHandle,
};
use nym_topology::{NymRouteProvider, NymTopology};
use std::pin::Pin;
use std::sync::Arc;
use std::task::{Context, Poll};
use tokio::sync::RwLockReadGuard;

/// Client connected to the Nym mixnet.
pub struct MixnetClient {
    /// The nym address of this connected client.
    pub(crate) nym_address: Recipient,

    pub(crate) identity_keys: Arc<ed25519::KeyPair>,

    /// Input to the client from the users perspective. This can be either data to send or control
    /// messages.
    pub(crate) client_input: ClientInput,

    /// Output from the client from the users perspective. This is typically messages arriving from
    /// the mixnet.
    #[allow(dead_code)]
    pub(crate) client_output: ClientOutput,

    /// The current state of the client that is exposed to the user. This includes things like
    /// current message send queue length.
    pub(crate) client_state: ClientState,

    /// A channel for messages arriving from the mixnet after they have been reconstructed.
    pub(crate) reconstructed_receiver: ReconstructedMessagesReceiver,

    /// A channel for sending stats event to be reported.
    pub(crate) stats_events_reporter: ClientStatsSender,

    /// The task manager that controls all the spawned tasks that the clients uses to do it's job.
    pub(crate) task_handle: TaskHandle,
    pub(crate) packet_type: Option<PacketType>,

    // internal state used for the `Stream` implementation
    _buffered: Vec<ReconstructedMessage>,
    pub(crate) client_request_sender: ClientRequestSender,
    pub(crate) forget_me: ForgetMe,
}

impl MixnetClient {
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn new(
        nym_address: Recipient,
        identity_keys: Arc<ed25519::KeyPair>,
        client_input: ClientInput,
        client_output: ClientOutput,
        client_state: ClientState,
        reconstructed_receiver: ReconstructedMessagesReceiver,
        stats_events_reporter: ClientStatsSender,
        task_handle: TaskHandle,
        packet_type: Option<PacketType>,
        client_request_sender: ClientRequestSender,
        forget_me: ForgetMe,
    ) -> Self {
        Self {
            nym_address,
            identity_keys,
            client_input,
            client_output,
            client_state,
            reconstructed_receiver,
            stats_events_reporter,
            task_handle,
            packet_type,
            _buffered: Vec::new(),
            client_request_sender,
            forget_me,
        }
    }

    /// Create a new client and connect to the mixnet using ephemeral in-memory keys that are
    /// discarded at application close.
    ///
    /// # Examples
    ///
    /// ```no_run
    /// use nym_sdk::mixnet;
    ///
    /// #[tokio::main]
    /// async fn main() {
    ///     let mut client = mixnet::MixnetClient::connect_new().await;
    /// }
    ///
    /// ```
    pub async fn connect_new() -> Result<Self> {
        MixnetClientBuilder::new_ephemeral()
            .build()?
            .connect_to_mixnet()
            .await
    }

    /// Get the nym address for this client, if it is available. The nym address is composed of the
    /// client identity, the client encryption key, and the gateway identity.
    pub fn nym_address(&self) -> &Recipient {
        &self.nym_address
    }

    pub fn client_request_sender(&self) -> ClientRequestSender {
        self.client_request_sender.clone()
    }

    /// Get the client's identity keys.
    pub fn identity_keypair(&self) -> Arc<ed25519::KeyPair> {
        self.identity_keys.clone()
    }

    /// Sign a message with the client's private identity key.
    pub fn sign(&self, data: &[u8]) -> ed25519::Signature {
        self.identity_keys.private_key().sign(data)
    }

    /// Sign a message with the client's private identity key and return it as a base58 encoded
    /// signature.
    pub fn sign_text(&self, text: &str) -> String {
        self.identity_keys.private_key().sign_text(text)
    }

    /// Get gateway connection information, like the file descriptor of the WebSocket
    pub fn gateway_connection(&self) -> GatewayConnection {
        self.client_state.gateway_connection
    }

    /// Get a shallow clone of [`MixnetClientSender`]. Useful if you want split the send and
    /// receive logic in different locations.
    pub fn split_sender(&self) -> MixnetClientSender {
        MixnetClientSender {
            client_input: self.client_input.clone(),
            packet_type: self.packet_type,
        }
    }

    /// Get a shallow clone of [`ConnectionCommandSender`]. This is useful if you want to e.g
    /// explicitly close a transmission lane that is still sending data even though it should
    /// cancel.
    pub fn connection_command_sender(&self) -> ConnectionCommandSender {
        self.client_input.connection_command_sender.clone()
    }

    /// Get a shallow clone of [`LaneQueueLengths`]. This is useful to manually implement some form
    /// of backpressure logic.
    pub fn shared_lane_queue_lengths(&self) -> LaneQueueLengths {
        self.client_state.shared_lane_queue_lengths.clone()
    }

    /// Change the network topology used by this client for constructing sphinx packets into the
    /// provided one.
    pub async fn manually_overwrite_topology(&self, new_topology: NymTopology) {
        self.client_state
            .topology_accessor
            .manually_change_topology(new_topology)
            .await
    }

    /// Gets the value of the currently used network topology.
    pub async fn read_current_route_provider(&self) -> Option<RwLockReadGuard<NymRouteProvider>> {
        self.client_state
            .topology_accessor
            .current_route_provider()
            .await
    }

    /// Restore default topology refreshing behaviour of this client.
    pub fn restore_automatic_topology_refreshing(&self) {
        self.client_state.topology_accessor.release_manual_control()
    }

    /// Wait for messages from the mixnet
    pub async fn wait_for_messages(&mut self) -> Option<Vec<ReconstructedMessage>> {
        self.reconstructed_receiver.next().await
    }

    /// Provide a callback to execute on incoming messages from the mixnet.
    pub async fn on_messages<F>(&mut self, fun: F)
    where
        F: Fn(ReconstructedMessage),
    {
        while let Some(msgs) = self.wait_for_messages().await {
            for msg in msgs {
                fun(msg)
            }
        }
    }

    pub fn send_stats_event(&self, event: ClientStatsEvents) {
        self.stats_events_reporter.report(event);
    }

    /// Get a clone of stats_events_reporter for easier use
    pub fn stats_events_reporter(&self) -> ClientStatsSender {
        self.stats_events_reporter.clone()
    }

    /// Disconnect from the mixnet. Currently it is not supported to reconnect a disconnected
    /// client.
    pub async fn disconnect(mut self) {
        if self.forget_me.any() {
            log::debug!("Sending forget me request: {:?}", self.forget_me);
            match self.send_forget_me().await {
                Ok(_) => (),
                Err(e) => error!("Failed to send forget me request: {}", e),
            };
            tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
        }

        if let TaskHandle::Internal(task_manager) = &mut self.task_handle {
            task_manager.signal_shutdown().ok();
            task_manager.wait_for_shutdown().await;
        }

        // note: it's important to take ownership of the struct as if the shutdown is `TaskHandle::External`,
        // it must be dropped to finalize the shutdown
    }

    pub async fn send_forget_me(&self) -> Result<()> {
        let client_request = ClientRequest::ForgetMe {
            client: self.forget_me.client(),
            stats: self.forget_me.stats(),
        };
        match self.client_request_sender.send(client_request).await {
            Ok(_) => Ok(()),
            Err(e) => {
                error!("Failed to send forget me request: {}", e);
                Err(Error::MessageSendingFailure)
            }
        }
    }
}

#[derive(Clone)]
pub struct MixnetClientSender {
    client_input: ClientInput,
    packet_type: Option<PacketType>,
}

impl Stream for MixnetClient {
    type Item = ReconstructedMessage;

    fn poll_next(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        if let Some(next) = self._buffered.pop() {
            cx.waker().wake_by_ref();
            return Poll::Ready(Some(next));
        }
        match ready!(Pin::new(&mut self.reconstructed_receiver).poll_next(cx)) {
            None => Poll::Ready(None),
            Some(mut msgs) => {
                // the vector itself should never be empty
                if let Some(next) = msgs.pop() {
                    // there's more than a single message - buffer them and wake the waker
                    // to get polled again immediately
                    if !msgs.is_empty() {
                        self._buffered = msgs;
                        cx.waker().wake_by_ref();
                    }
                    Poll::Ready(Some(next))
                } else {
                    // I *think* this happens for SURBs, but I'm not 100% sure. Nonetheless it's
                    // beneign, but let's log it here anyway as a reminder
                    debug!("the reconstructed messages vector is empty");
                    cx.waker().wake_by_ref();
                    Poll::Pending
                }
            }
        }
    }
}

#[async_trait]
impl MixnetMessageSender for MixnetClient {
    fn packet_type(&self) -> Option<PacketType> {
        self.packet_type
    }

    async fn send(&self, message: InputMessage) -> Result<()> {
        self.client_input
            .send(message)
            .await
            .map_err(|_| Error::MessageSendingFailure)
    }
}

#[async_trait]
impl MixnetMessageSender for MixnetClientSender {
    fn packet_type(&self) -> Option<PacketType> {
        self.packet_type
    }

    async fn send(&self, message: InputMessage) -> Result<()> {
        self.client_input
            .send(message)
            .await
            .map_err(|_| Error::MessageSendingFailure)
    }
}
```

paths.rs
```rust
// Copyright 2022-2024 - Nym Technologies SA <contact@nymtech.net>
// SPDX-License-Identifier: Apache-2.0

use crate::error::{Error, Result};
use nym_client_core::client::base_client::storage::OnDiskGatewaysDetails;
use nym_client_core::client::base_client::{non_wasm_helpers, storage};
use nym_client_core::client::key_manager::persistence::OnDiskKeys;
use nym_client_core::client::replies::reply_storage::fs_backend;
use nym_client_core::config;
use nym_client_core::config::disk_persistence::CommonClientPaths;
use nym_client_core::config::disk_persistence::{
    ClientKeysPaths, DEFAULT_ACK_KEY_FILENAME, DEFAULT_CREDENTIALS_DB_FILENAME,
    DEFAULT_GATEWAYS_DETAILS_DB_FILENAME, DEFAULT_PRIVATE_ENCRYPTION_KEY_FILENAME,
    DEFAULT_PRIVATE_IDENTITY_KEY_FILENAME, DEFAULT_PUBLIC_ENCRYPTION_KEY_FILENAME,
    DEFAULT_PUBLIC_IDENTITY_KEY_FILENAME, DEFAULT_REPLY_SURB_DB_FILENAME,
};
use nym_credential_storage::persistent_storage::PersistentStorage as PersistentCredentialStorage;
use std::path::{Path, PathBuf};

/// Set of storage paths that the client will use if it is setup to persist keys, credentials, and
/// reply-SURBs.
#[derive(Clone, Debug)]
pub struct StoragePaths {
    /// Client private identity key
    pub private_identity: PathBuf,

    /// Client public identity key
    pub public_identity: PathBuf,

    /// Client private encryption key
    pub private_encryption: PathBuf,

    /// Client public encryption key
    pub public_encryption: PathBuf,

    /// Key for handling acks
    pub ack_key: PathBuf,

    /// The database containing credentials
    pub credential_database_path: PathBuf,

    /// The database storing reply surbs in-between sessions
    pub reply_surb_database_path: PathBuf,

    /// Details of the used gateways
    pub gateway_registrations: PathBuf,
}

impl StoragePaths {
    /// Create a set of storage paths from a given directory.
    ///
    /// # Errors
    ///
    /// This function will return an error if it is passed a path to an existing file instead of a
    /// directory.
    pub fn new_from_dir<P: AsRef<Path>>(dir: P) -> Result<Self> {
        let dir = dir.as_ref();
        if dir.is_file() {
            return Err(Error::ExpectedDirectory(dir.to_owned()));
        }

        Ok(Self {
            private_identity: dir.join(DEFAULT_PRIVATE_IDENTITY_KEY_FILENAME),
            public_identity: dir.join(DEFAULT_PUBLIC_IDENTITY_KEY_FILENAME),
            private_encryption: dir.join(DEFAULT_PRIVATE_ENCRYPTION_KEY_FILENAME),
            public_encryption: dir.join(DEFAULT_PUBLIC_ENCRYPTION_KEY_FILENAME),
            ack_key: dir.join(DEFAULT_ACK_KEY_FILENAME),
            credential_database_path: dir.join(DEFAULT_CREDENTIALS_DB_FILENAME),
            reply_surb_database_path: dir.join(DEFAULT_REPLY_SURB_DB_FILENAME),
            gateway_registrations: dir.join(DEFAULT_GATEWAYS_DETAILS_DB_FILENAME),
        })
    }

    /// Instantiates default full client storage backend with default configuration.
    pub async fn initialise_default_persistent_storage(
        &self,
    ) -> Result<storage::OnDiskPersistent, Error> {
        Ok(storage::OnDiskPersistent::new(
            self.on_disk_key_storage_spec(),
            self.default_persistent_fs_reply_backend().await?,
            self.persistent_credential_storage().await?,
            self.on_disk_gateway_details_storage().await?,
        ))
    }

    /// Instantiates default full client storage backend with the provided configuration.
    pub async fn initialise_persistent_storage(
        &self,
        config: &config::DebugConfig,
    ) -> Result<storage::OnDiskPersistent, Error> {
        Ok(storage::OnDiskPersistent::new(
            self.on_disk_key_storage_spec(),
            self.persistent_fs_reply_backend(&config.reply_surbs)
                .await?,
            self.persistent_credential_storage().await?,
            self.on_disk_gateway_details_storage().await?,
        ))
    }

    /// Instantiates default coconut credential storage.
    pub async fn persistent_credential_storage(
        &self,
    ) -> Result<PersistentCredentialStorage, Error> {
        PersistentCredentialStorage::init(&self.credential_database_path)
            .await
            .map_err(|source| Error::CredentialStorageError {
                source: Box::new(source),
            })
    }

    /// Instantiates default reply surb storage backend with default configuration.
    pub async fn default_persistent_fs_reply_backend(&self) -> Result<fs_backend::Backend, Error> {
        self.persistent_fs_reply_backend(&Default::default()).await
    }

    /// Instantiates default reply surb storage backend with the provided metadata config.
    pub async fn persistent_fs_reply_backend(
        &self,
        surb_config: &config::ReplySurbs,
    ) -> Result<fs_backend::Backend, Error> {
        Ok(non_wasm_helpers::setup_fs_reply_surb_backend(
            &self.reply_surb_database_path,
            surb_config,
        )
        .await?)
    }

    /// Instantiates default persistent key storage.
    pub fn on_disk_key_storage_spec(&self) -> OnDiskKeys {
        OnDiskKeys::new(self.client_keys_paths())
    }

    pub async fn on_disk_gateway_details_storage(&self) -> Result<OnDiskGatewaysDetails, Error> {
        Ok(non_wasm_helpers::setup_fs_gateways_storage(&self.gateway_registrations).await?)
    }

    pub fn credential_database_paths(&self) -> Vec<PathBuf> {
        Self::with_sqlite_journal_paths(&self.credential_database_path)
    }

    pub fn reply_surb_database_paths(&self) -> Vec<PathBuf> {
        Self::with_sqlite_journal_paths(&self.reply_surb_database_path)
    }

    pub fn gateway_registrations_paths(&self) -> Vec<PathBuf> {
        Self::with_sqlite_journal_paths(&self.gateway_registrations)
    }

    fn client_keys_paths(&self) -> ClientKeysPaths {
        ClientKeysPaths {
            private_identity_key_file: self.private_identity.clone(),
            public_identity_key_file: self.public_identity.clone(),
            private_encryption_key_file: self.private_encryption.clone(),
            public_encryption_key_file: self.public_encryption.clone(),
            ack_key_file: self.ack_key.clone(),
        }
    }

    /// Returns a list of paths that include the sqlite database and journal files (wal, shm)
    fn with_sqlite_journal_paths<P: AsRef<Path>>(db_file: P) -> Vec<PathBuf> {
        ["-shm", "-wal"]
            .iter()
            .map(|ext_suffix| {
                let mut new_ext = db_file.as_ref().extension().unwrap_or_default().to_owned();
                new_ext.push(ext_suffix);
                db_file.as_ref().with_extension(new_ext)
            })
            .chain([db_file.as_ref().to_path_buf()])
            .collect()
    }
}

impl From<StoragePaths> for CommonClientPaths {
    fn from(value: StoragePaths) -> Self {
        CommonClientPaths {
            keys: ClientKeysPaths {
                private_identity_key_file: value.private_identity,
                public_identity_key_file: value.public_identity,
                private_encryption_key_file: value.private_encryption,
                public_encryption_key_file: value.public_encryption,
                ack_key_file: value.ack_key,
            },
            gateway_registrations: value.gateway_registrations,
            credentials_database: value.credential_database_path,
            reply_surb_database: value.reply_surb_database_path,
        }
    }
}

impl From<CommonClientPaths> for StoragePaths {
    fn from(value: CommonClientPaths) -> Self {
        StoragePaths {
            private_identity: value.keys.private_identity_key_file,
            public_identity: value.keys.public_identity_key_file,
            private_encryption: value.keys.private_encryption_key_file,
            public_encryption: value.keys.public_encryption_key_file,
            ack_key: value.keys.ack_key_file,
            credential_database_path: value.credentials_database,
            reply_surb_database_path: value.reply_surb_database,
            gateway_registrations: value.gateway_registrations,
        }
    }
}
```

socks5_client.rs
```rust
use nym_client_core::client::base_client::ClientState;
use nym_socks5_client_core::config::Socks5;
use nym_sphinx::addressing::clients::Recipient;
use nym_task::{connections::LaneQueueLengths, TaskHandle};

use nym_topology::NymTopology;

use crate::mixnet::client::MixnetClientBuilder;
use crate::Result;

/// Client connected to the Nym mixnet.
pub struct Socks5MixnetClient {
    /// The nym address of this connected client.
    pub(crate) nym_address: Recipient,

    /// The current state of the client that is exposed to the user. This includes things like
    /// current message send queue length.
    pub(crate) client_state: ClientState,

    /// The task manager that controls all the spawned tasks that the clients uses to do it's job.
    pub(crate) task_handle: TaskHandle,

    /// SOCKS5 configuration parameters.
    pub(crate) socks5_config: Socks5,
}

impl Socks5MixnetClient {
    /// Create a new client and connect to a service provider over the mixnet via SOCKS5 using
    /// ephemeral in-memory keys that are discarded at application close.
    ///
    /// # Examples
    ///
    /// ```no_run
    /// use nym_sdk::mixnet;
    ///
    /// #[tokio::main]
    /// async fn main() {
    ///     let receiving_client = mixnet::MixnetClient::connect_new().await.unwrap();
    ///     let mut client = mixnet::Socks5MixnetClient::connect_new(receiving_client.nym_address().to_string()).await;
    /// }
    ///
    /// ```
    pub async fn connect_new<S: Into<String>>(provider_mix_address: S) -> Result<Self> {
        MixnetClientBuilder::new_ephemeral()
            .socks5_config(Socks5::new(provider_mix_address))
            .build()?
            .connect_to_mixnet_via_socks5()
            .await
    }

    /// Get the nym address for this client, if it is available. The nym address is composed of the
    /// client identity, the client encryption key, and the gateway identity.
    pub fn nym_address(&self) -> &Recipient {
        &self.nym_address
    }

    /// Get the SOCKS5 proxy URL that a HTTP(S) client can connect to.
    pub fn socks5_url(&self) -> String {
        format!("socks5h://{}", self.socks5_config.bind_address)
    }

    /// Get a shallow clone of [`LaneQueueLengths`]. This is useful to manually implement some form
    /// of backpressure logic.
    pub fn shared_lane_queue_lengths(&self) -> LaneQueueLengths {
        self.client_state.shared_lane_queue_lengths.clone()
    }

    /// Change the network topology used by this client for constructing sphinx packets into the
    /// provided one.
    pub async fn manually_overwrite_topology(&self, new_topology: NymTopology) {
        self.client_state
            .topology_accessor
            .manually_change_topology(new_topology)
            .await
    }

    /// Restore default topology refreshing behaviour of this client.
    pub fn restore_automatic_topology_refreshing(&self) {
        self.client_state.topology_accessor.release_manual_control()
    }

    /// Disconnect from the mixnet. Currently it is not supported to reconnect a disconnected
    /// client.
    pub async fn disconnect(mut self) {
        if let TaskHandle::Internal(task_manager) = &mut self.task_handle {
            task_manager.signal_shutdown().ok();
            task_manager.wait_for_shutdown().await;
        }

        // note: it's important to take ownership of the struct as if the shutdown is `TaskHandle::External`,
        // it must be dropped to finalize the shutdown
    }
}
```

traits.rs
```rust
// Copyright 2023 - Nym Technologies SA <contact@nymtech.net>
// SPDX-License-Identifier: Apache-2.0

use crate::mixnet::{AnonymousSenderTag, IncludedSurbs, Recipient};
use crate::Result;
use async_trait::async_trait;
use nym_client_core::client::inbound_messages::InputMessage;
use nym_sphinx::params::PacketType;
use nym_task::connections::TransmissionLane;

// defined to guarantee common interface regardless of whether you're using the full client
// or just the sending handler
#[async_trait]
pub trait MixnetMessageSender {
    fn packet_type(&self) -> Option<PacketType> {
        None
    }

    /// Sends a [`InputMessage`] to the mixnet. This is the most low-level sending function, for
    /// full customization.
    async fn send(&self, message: InputMessage) -> Result<()>;

    /// Sends data to the supplied Nym address with the default surb behaviour.
    ///
    /// # Example
    ///
    /// ```no_run
    /// use nym_sdk::mixnet::{self, MixnetMessageSender};
    ///
    /// #[tokio::main]
    /// async fn main() {
    ///     let address = "foobar";
    ///     let recipient = mixnet::Recipient::try_from_base58_string(address).unwrap();
    ///     let mut client = mixnet::MixnetClient::connect_new().await.unwrap();
    ///     client.send_plain_message(recipient, "hi").await.unwrap();
    /// }
    /// ```
    async fn send_plain_message<M>(&self, address: Recipient, message: M) -> Result<()>
    where
        M: AsRef<[u8]> + Send,
    {
        self.send_message(address, message, IncludedSurbs::default())
            .await
    }

    /// Sends bytes to the supplied Nym address. There is the option to specify the number of
    /// reply-SURBs to include.
    ///
    /// # Example
    ///
    /// ```no_run
    /// use nym_sdk::mixnet::{self, MixnetMessageSender};
    ///
    /// #[tokio::main]
    /// async fn main() {
    ///     let address = "foobar";
    ///     let recipient = mixnet::Recipient::try_from_base58_string(address).unwrap();
    ///     let mut client = mixnet::MixnetClient::connect_new().await.unwrap();
    ///     let surbs = mixnet::IncludedSurbs::default();
    ///     client.send_message(recipient, "hi".to_owned().into_bytes(), surbs).await.unwrap();
    /// }
    /// ```
    async fn send_message<M>(
        &self,
        address: Recipient,
        message: M,
        surbs: IncludedSurbs,
    ) -> Result<()>
    where
        M: AsRef<[u8]> + Send,
    {
        let lane = TransmissionLane::General;
        let input_msg = match surbs {
            IncludedSurbs::Amount(surbs) => InputMessage::new_anonymous(
                address,
                message.as_ref().to_vec(),
                surbs,
                lane,
                self.packet_type(),
            ),
            IncludedSurbs::ExposeSelfAddress => InputMessage::new_regular(
                address,
                message.as_ref().to_vec(),
                lane,
                self.packet_type(),
            ),
        };
        self.send(input_msg).await
    }

    /// Sends reply data to the supplied anonymous recipient.
    ///
    /// # Example
    ///
    /// ```no_run
    /// use nym_sdk::mixnet::{self, MixnetMessageSender};
    ///
    /// #[tokio::main]
    /// async fn main() {
    ///     let mut client = mixnet::MixnetClient::connect_new().await.unwrap();
    ///     // note: the tag is something you would have received from a remote client sending you surbs!
    ///     let tag = mixnet::AnonymousSenderTag::try_from_base58_string("foobar").unwrap();
    ///     client.send_reply(tag, b"hi").await.unwrap();
    /// }
    /// ```
    async fn send_reply<M>(&self, recipient_tag: AnonymousSenderTag, message: M) -> Result<()>
    where
        M: AsRef<[u8]> + Send,
    {
        let lane = TransmissionLane::General;
        let input_msg = InputMessage::new_reply(
            recipient_tag,
            message.as_ref().to_vec(),
            lane,
            self.packet_type(),
        );
        self.send(input_msg).await
    }
}
```