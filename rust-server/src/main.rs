use anyhow::Result;
use futures::StreamExt;
use libp2p::{
    core::{muxing::StreamMuxerBox},
    gossipsub,
    identity,
    kad::record::store::{RecordStore, MemoryStore},
    kad::{GetClosestPeersError, Kademlia, KademliaConfig, KademliaEvent, QueryResult},
    PeerId,
    ping,
    swarm::{keep_alive, NetworkBehaviour, Swarm, SwarmBuilder},
    Transport,
    webrtc,
};
use rand::thread_rng;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::time::Duration;

// TODO: replace with our private bootstrap node
const BOOTNODES: [&str; 1] = [
    "QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
    // "QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
    // "QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb",
    // "QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt",
];

/// An example WebRTC server that will accept connections
#[tokio::main]
async fn main() -> Result<()> {
    env_logger::init();

    let mut swarm = create_swarm::<MemoryStore>()?;

    swarm.listen_on("/ip4/127.0.0.1/udp/0/webrtc".parse()?)?;

    loop {
        let event = swarm.next().await.unwrap();
        eprintln!("New event: {event:?}")
    }
}

#[derive(NetworkBehaviour)]
struct Behaviour<T: RecordStore + std::marker::Send + 'static> {
    gossipsub: gossipsub::Behaviour,
    kademlia: Kademlia<T>,
    keep_alive: keep_alive::Behaviour,
    ping: ping::Behaviour,
}

fn create_swarm<T: RecordStore + std::marker::Send + 'static>() -> Result<Swarm<Behaviour<MemoryStore>>> {
    let local_key = identity::Keypair::generate_ed25519();
    let local_peer_id = PeerId::from(local_key.public());
    println!("Local peer id: {local_peer_id}");

    // Create a Kademlia behaviour.
    let mut cfg = KademliaConfig::default();
    cfg.set_query_timeout(Duration::from_secs(5 * 60));
    let store = MemoryStore::new(local_peer_id);
    let mut kad_behaviour = Kademlia::with_config(local_peer_id, store, cfg);

    // Add the bootnodes to the local routing table. `libp2p-dns` built
    // into the `transport` resolves the `dnsaddr` when Kademlia tries
    // to dial these nodes.
    for peer in &BOOTNODES {
                                                    // TODO: update this
        kad_behaviour.add_address(&peer.parse()?, "/dnsaddr/bootstrap.libp2p.io".parse()?);
    }

    // To content-address message, we can take the hash of message and use it as an ID.
    let message_id_fn = |message: &gossipsub::Message| {
        let mut s = DefaultHasher::new();
        message.data.hash(&mut s);
        gossipsub::MessageId::from(s.finish().to_string())
    };

    // Set a custom gossipsub configuration
    let gossipsub_config = gossipsub::ConfigBuilder::default()
        .heartbeat_interval(Duration::from_secs(10)) // This is set to aid debugging by not cluttering the log space
        .validation_mode(gossipsub::ValidationMode::Permissive) // This sets the kind of message validation. The default is Strict (enforce message signing)
        .message_id_fn(message_id_fn) // content-address messages. No two messages of the same content will be propagated.
        .build()
        .expect("Valid config");

    // build a gossipsub network behaviour
    let mut gossipsub = gossipsub::Behaviour::new(
        gossipsub::MessageAuthenticity::Signed(local_key.clone()),
        gossipsub_config,
    )
    .expect("Correct configuration");

    // // Create a Gossipsub topic
    // let topic = gossipsub::IdentTopic::new("universal-connectivity");

    // // subscribes to our topic
    // gossipsub.subscribe(&topic)?;

    let transport = webrtc::tokio::Transport::new(
        local_key.clone(),
        webrtc::tokio::Certificate::generate(&mut thread_rng())?,
    );

    let transport = transport
        .map(|(local_peer_id, conn), _| (local_peer_id, StreamMuxerBox::new(conn)))
        .boxed();

    let behaviour = Behaviour { gossipsub, kademlia: kad_behaviour, keep_alive: keep_alive::Behaviour::default(), ping: ping::Behaviour::default() };
    Ok(SwarmBuilder::with_tokio_executor(transport, behaviour, local_peer_id).build())
}
