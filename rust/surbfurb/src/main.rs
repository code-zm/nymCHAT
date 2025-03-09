use nym_sphinx::message::NymMessage;
use nym_sphinx::routing::generate_hop_delays;
use nym_sphinx::anonymous_replies::ReplySurb;
use nym_crypto::asymmetric::{encryption::KeyPair as EncryptionKeyPair, identity::KeyPair as IdentityKeyPair};

use nym_sdk::mixnet::{MixnetClient, Recipient, AnonymousSenderTag, MixnetMessageSender, InputMessage, TransmissionLane};
use nym_sphinx_types::SURBMaterial;
use nym_sphinx::anonymous_replies::requests::{RepliableMessage, RepliableMessageContent};
use nym_topology::NymRouteProvider;

use rand::{rngs::OsRng, CryptoRng, RngCore, seq::SliceRandom};
use std::time::Duration;
use tokio::signal;
use futures::StreamExt;
use std::error::Error;

/// Generate a Real Reply SURB for a registered user.
fn generate_surb<R: RngCore + CryptoRng>(
    rng: &mut R,
    recipient: &Recipient,
    average_delay: Duration,
    topology: &NymRouteProvider,
) -> Result<ReplySurb, Box<dyn Error>> {
    ReplySurb::construct(rng, recipient, average_delay, topology).map_err(|e| e.into())
}

/// Generate a Fake Reply SURB (FURB) for an unregistered user.
fn generate_furb<R: RngCore + CryptoRng>(
    rng: &mut R,
    username: &str,
    topology: &NymRouteProvider,
    average_delay: Duration,
) -> Result<ReplySurb, Box<dyn Error>> {
    let fake_identity = IdentityKeyPair::new(rng);
    let fake_encryption = EncryptionKeyPair::new(rng);
    let gateway_nodes: Vec<_> = topology.topology.entry_gateways().collect();
    
    if gateway_nodes.is_empty() {
        return Err("No gateways available in the topology!".into());
    }
    
    let chosen_gateway = gateway_nodes.choose(rng).ok_or("Failed to select a gateway!")?.identity_key;
    let fake_recipient = Recipient::new(
        *fake_identity.public_key(),
        *fake_encryption.public_key(),
        chosen_gateway,
    );

    ReplySurb::construct(rng, &fake_recipient, average_delay, topology).map_err(|e| e.into())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    println!("🔌 Connecting to Nym Mixnet...");
    nym_bin_common::logging::setup_logging();

    let mut client = MixnetClient::connect_new().await?;

    // Read the current topology
    let topology = match client.read_current_route_provider().await {
        Some(topology) => topology.clone(),
        None => {
            eprintln!("⚠️ Failed to fetch updated topology, using default fallback.");
            NymRouteProvider::default()
        }
    };

    // Get our own recipient address
    let recipient = client.nym_address().clone();
    println!("📡 Our Nym address: {}", recipient);

    let mut rng = OsRng;

    // Generate a Fake SURB (FURB)
    let fake_surb = match generate_furb(&mut rng, "fake_user", &topology, Duration::from_millis(100)) {
        Ok(furb) => {
            println!("✅ Successfully generated Fake SURB (FURB).");
            furb
        },
        Err(e) => {
            eprintln!("❌ Failed to generate Fake SURB: {}", e);
            return Err(e);
        }
    };

    // Generate a Real Reply SURB
    let real_surb = match generate_surb(&mut rng, &recipient, Duration::from_millis(100), &topology) {
        Ok(surb) => {
            println!("✅ Successfully generated Real SURB.");
            surb
        },
        Err(e) => {
            eprintln!("❌ Failed to generate Real SURB: {}", e);
            return Err(e);
        }
    };

    println!("🚀 Sending messages...");

    // Send message with REAL SURB
    let sender_tag_real = AnonymousSenderTag::new_random(&mut rng);
    let repliable_msg_real = RepliableMessage::new_data(
        b"Hello with REAL SURB".to_vec(),
        sender_tag_real,
        vec![real_surb],
    );
    let serialized_msg_real = repliable_msg_real.into_bytes();

    let input_msg_real = InputMessage::Regular {
        recipient: recipient.clone(),
        data: serialized_msg_real,
        lane: TransmissionLane::General,
    };

    if let Err(e) = client.send(input_msg_real).await {
        eprintln!("❌ Failed to send message with REAL SURB: {}", e);
        return Err(e.into());
    } else {
        println!("✅ Successfully sent message with REAL SURB!");
    }

    // Send message with FAKE SURB
    let sender_tag_fake = AnonymousSenderTag::new_random(&mut rng);
    let repliable_msg_fake = RepliableMessage::new_data(
        b"Hello with FAKE SURB".to_vec(),
        sender_tag_fake,
        vec![fake_surb],
    );
    let serialized_msg_fake = repliable_msg_fake.into_bytes();

    let input_msg_fake = InputMessage::Regular {
        recipient: recipient.clone(),
        data: serialized_msg_fake,
        lane: TransmissionLane::General,
    };

    if let Err(e) = client.send(input_msg_fake).await {
        eprintln!("❌ Failed to send message with FAKE SURB: {}", e);
        return Err(e.into());
    } else {
        println!("✅ Successfully sent message with FAKE SURB!");
    }

    // Start listening for replies
    println!("📡 Listening for incoming messages...");
    loop {
        tokio::select! {
            _ = signal::ctrl_c() => {
                println!("🛑 Ctrl+C detected! Stopping...");
                break;
            }
            received = client.next() => {
                if let Some(received) = received {
                    match RepliableMessage::try_from_bytes(&received.message) {
                        Ok(repliable_msg) => {
                            // Extract and print only the actual message
                            if let RepliableMessageContent::Data { message, .. } = repliable_msg.content {
                                match String::from_utf8(message.clone()) {
                                    Ok(text) => println!("📩 Received message: {}", text),
                                    Err(_) => println!("⚠️ Received message could not be parsed as UTF-8."),
                                }
                            } else {
                                println!("⚠️ Received an unknown message type.");
                            }

                            if let Some(sender_tag) = Some(repliable_msg.sender_tag) {
                                println!("↩️ Replying to {} anonymously using SURB...", sender_tag);
                                if let Err(e) = client.send_reply(sender_tag, b"Hello back with SURB!").await {
                                    eprintln!("❌ Failed to send reply: {}", e);
                                }
                            } else {
                                println!("⚠️ No senderTag found, cannot reply via SURB.");
                            }
                        }
                        Err(_) => println!("⚠️ Received a non-repliable message."),
                    }
                }
            }
        }
    }



    // Disconnect the client
    println!("🔌 Disconnecting from Mixnet...");
    client.disconnect().await;
    println!("✅ Successfully disconnected.");

    Ok(())
}

