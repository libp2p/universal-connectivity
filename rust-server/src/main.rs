use anyhow::Result;
use futures::StreamExt;
use libp2p::{
    core::muxing::StreamMuxerBox,
    gossipsub, identify, identity,
    multiaddr::Protocol,
    ping,
    swarm::{keep_alive, NetworkBehaviour, Swarm, SwarmBuilder, SwarmEvent},
    webrtc, Multiaddr, PeerId, Transport,
};
use rand::thread_rng;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::io;
use std::time::{Duration, Instant};


/// An example WebRTC server that will accept connections
#[tokio::main]
async fn main() -> Result<()> {
    env_logger::init();

    let mut swarm = create_swarm()?;
    swarm.listen_on(format!("/ip4/127.0.0.1/udp/0/webrtc").parse()?)?;

    let now = Instant::now();
    loop {
        let event = swarm.next().await.unwrap();
        eprintln!("New event: {event:?}");
        match event {
            SwarmEvent::NewListenAddr { address, .. } => {
                let p2p_address = address.with(Protocol::P2p((*swarm.local_peer_id()).into()));
                eprintln!("p2p address: {p2p_address:?}")
            },
            _ => {}
        }
        let peers: Vec<_> = swarm.behaviour().gossipsub.all_peers().collect();
        eprintln!("Peers: {peers:?}");
        let peers: Vec<_> = swarm.behaviour().gossipsub.all_mesh_peers().collect();
        eprintln!("Mesh peers: {peers:?}");


        let elapsed_secs = now.elapsed().as_secs();
        eprintln!("elapsed seconds: {}", elapsed_secs);

        let message = "Hello world! sent at : ".to_owned() + &elapsed_secs.clone().to_string() + " seconds.";

        if elapsed_secs % 2 == 0 {
            dbg!(swarm
                .behaviour_mut()
                .gossipsub
                .publish(gossipsub::IdentTopic::new("universal-connectivity"), message.as_bytes()));
        }
    }
}

#[derive(NetworkBehaviour)]
struct Behaviour {
    gossipsub: gossipsub::Behaviour,
    identify: identify::Behaviour,
    // kademlia: Kademlia<MemoryStore>,
    keep_alive: keep_alive::Behaviour,
    ping: ping::Behaviour,
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
        .validation_mode(gossipsub::ValidationMode::Permissive) // This sets the kind of message validation. The default is Strict (enforce message signing)
        .message_id_fn(message_id_fn) // content-address messages. No two messages of the same content will be propagated.
        .mesh_outbound_min(1)
        .mesh_n_low(1)
        .flood_publish(true)
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

    let identify_config = identify::Behaviour::new(identify::Config::new(
        "/ipfs/0.1.0".into(),
        local_key.public().clone(),
    ));

    let transport = transport
        .map(|(local_peer_id, conn), _| (local_peer_id, StreamMuxerBox::new(conn)))
        .boxed();

    let behaviour = Behaviour {
        gossipsub,
        identify: identify_config,
        keep_alive: keep_alive::Behaviour::default(),
        ping: ping::Behaviour::default(),
    };
    Ok(SwarmBuilder::with_tokio_executor(transport, behaviour, local_peer_id).build())
}
