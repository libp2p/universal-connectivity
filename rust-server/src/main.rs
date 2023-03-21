use anyhow::Result;
use futures::StreamExt;
use libp2p::{
    core::{muxing::StreamMuxerBox},
    gossipsub,
    identity,
    PeerId,
    swarm::{NetworkBehaviour, Swarm, SwarmBuilder},
    Transport,
    webrtc,
};
use rand::thread_rng;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::time::Duration;

/// An example WebRTC server that will accept connections and run the ping protocol on them.
#[tokio::main]
async fn main() -> Result<()> {
    let mut swarm = create_swarm()?;

    swarm.listen_on("/ip4/127.0.0.1/udp/0/webrtc".parse()?)?;

    loop {
        let event = swarm.next().await.unwrap();
        eprintln!("New event: {event:?}")
    }
}

// We create a custom network behaviour with Gossipsub
#[derive(NetworkBehaviour)]
struct Behaviour {
    gossipsub: gossipsub::Behaviour,
}

fn create_swarm() -> Result<Swarm<Behaviour>> {
    let local_key = identity::Keypair::generate_ed25519();
    let local_peer_id = PeerId::from(local_key.public());
    println!("Local peer id: {local_peer_id}");

    // To content-address message, we can take the hash of message and use it as an ID.
    let message_id_fn = |message: &gossipsub::Message| {
        let mut s = DefaultHasher::new();
        message.data.hash(&mut s);
        gossipsub::MessageId::from(s.finish().to_string())
    };

    // Set a custom gossipsub configuration
    let gossipsub_config = gossipsub::ConfigBuilder::default()
        .heartbeat_interval(Duration::from_secs(10)) // This is set to aid debugging by not cluttering the log space
        .validation_mode(gossipsub::ValidationMode::Strict) // This sets the kind of message validation. The default is Strict (enforce message signing)
        .message_id_fn(message_id_fn) // content-address messages. No two messages of the same content will be propagated.
        .build()
        .expect("Valid config");

    // build a gossipsub network behaviour
    let mut gossipsub = gossipsub::Behaviour::new(
        gossipsub::MessageAuthenticity::Signed(local_key.clone()),
        gossipsub_config,
    )
    .expect("Correct configuration");

    // Create a Gossipsub topic
    let topic = gossipsub::IdentTopic::new("universal-connectivity");

    // subscribes to our topic
    gossipsub.subscribe(&topic)?;

    let transport = webrtc::tokio::Transport::new(
        local_key.clone(),
        webrtc::tokio::Certificate::generate(&mut thread_rng())?,
    );

    let transport = transport
        .map(|(local_peer_id, conn), _| (local_peer_id, StreamMuxerBox::new(conn)))
        .boxed();

    let behaviour = Behaviour { gossipsub };
    Ok(SwarmBuilder::with_tokio_executor(transport, behaviour, local_peer_id).build())
}
