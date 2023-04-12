use anyhow::Result;
use clap::Parser;
use futures::StreamExt;
use libp2p::{
    core::muxing::StreamMuxerBox,
    gossipsub, identify, identity,
    kad::record::store::MemoryStore,
    kad::{Kademlia, KademliaConfig},
    multiaddr::Protocol,
    ping, relay,
    swarm::{
        keep_alive, AddressRecord, AddressScore, NetworkBehaviour, Swarm, SwarmBuilder, SwarmEvent,
    },
    Multiaddr, PeerId, Transport,
};
use libp2p_webrtc as webrtc;
use log::{debug, error, info, warn};
use std::{
    borrow::Cow,
    collections::hash_map::DefaultHasher,
    fs::File,
    hash::{Hash, Hasher},
    io::{BufReader, Read},
    time::{Duration, Instant},
};

const TICK_INTERVAL: Duration = Duration::from_secs(15);
const KADEMLIA_PROTOCOL_NAME: &'static [u8] = b"/universal-connectivity/lan/kad/1.0.0";
const STATIC_CERTIFICATE: &'static [u8] = &[
    45, 45, 45, 45, 45, 66, 69, 71, 73, 78, 32, 69, 88, 80, 73, 82, 69, 83, 45, 45, 45, 45, 45, 10,
    65, 80, 102, 104, 110, 103, 56, 65, 65, 65, 65, 61, 10, 45, 45, 45, 45, 45, 69, 78, 68, 32, 69,
    88, 80, 73, 82, 69, 83, 45, 45, 45, 45, 45, 10, 10, 45, 45, 45, 45, 45, 66, 69, 71, 73, 78, 32,
    80, 82, 73, 86, 65, 84, 69, 95, 75, 69, 89, 45, 45, 45, 45, 45, 10, 77, 73, 71, 72, 65, 103,
    69, 65, 77, 66, 77, 71, 66, 121, 113, 71, 83, 77, 52, 57, 65, 103, 69, 71, 67, 67, 113, 71, 83,
    77, 52, 57, 65, 119, 69, 72, 66, 71, 48, 119, 97, 119, 73, 66, 65, 81, 81, 103, 105, 86, 56,
    82, 72, 69, 100, 118, 85, 101, 48, 57, 108, 80, 57, 83, 10, 104, 52, 78, 70, 73, 74, 69, 70,
    113, 88, 104, 88, 43, 68, 85, 97, 51, 76, 109, 88, 112, 79, 119, 115, 117, 76, 71, 104, 82, 65,
    78, 67, 65, 65, 84, 115, 69, 73, 65, 53, 121, 113, 67, 119, 56, 78, 122, 73, 87, 73, 114, 117,
    111, 86, 87, 43, 109, 116, 83, 113, 105, 70, 122, 106, 10, 50, 51, 77, 84, 43, 107, 88, 73, 52,
    77, 77, 49, 115, 52, 109, 65, 121, 122, 100, 82, 57, 90, 113, 115, 81, 70, 72, 43, 104, 55, 86,
    75, 106, 70, 67, 86, 122, 73, 86, 70, 52, 76, 47, 49, 97, 54, 81, 75, 47, 86, 81, 47, 53, 120,
    102, 66, 10, 45, 45, 45, 45, 45, 69, 78, 68, 32, 80, 82, 73, 86, 65, 84, 69, 95, 75, 69, 89,
    45, 45, 45, 45, 45, 10, 10, 45, 45, 45, 45, 45, 66, 69, 71, 73, 78, 32, 67, 69, 82, 84, 73, 70,
    73, 67, 65, 84, 69, 45, 45, 45, 45, 45, 10, 77, 73, 73, 66, 87, 84, 67, 66, 47, 54, 65, 68, 65,
    103, 69, 67, 65, 103, 104, 111, 117, 49, 43, 70, 77, 118, 103, 76, 88, 106, 65, 75, 66, 103,
    103, 113, 104, 107, 106, 79, 80, 81, 81, 68, 65, 106, 65, 104, 77, 82, 56, 119, 72, 81, 89, 68,
    86, 81, 81, 68, 68, 66, 90, 121, 10, 89, 50, 100, 108, 98, 105, 66, 122, 90, 87, 120, 109, 73,
    72, 78, 112, 90, 50, 53, 108, 90, 67, 66, 106, 90, 88, 74, 48, 77, 67, 65, 88, 68, 84, 99, 49,
    77, 68, 69, 119, 77, 84, 65, 119, 77, 68, 65, 119, 77, 70, 111, 89, 68, 122, 81, 119, 79, 84,
    89, 119, 77, 84, 65, 120, 10, 77, 68, 65, 119, 77, 68, 65, 119, 87, 106, 65, 104, 77, 82, 56,
    119, 72, 81, 89, 68, 86, 81, 81, 68, 68, 66, 90, 121, 89, 50, 100, 108, 98, 105, 66, 122, 90,
    87, 120, 109, 73, 72, 78, 112, 90, 50, 53, 108, 90, 67, 66, 106, 90, 88, 74, 48, 77, 70, 107,
    119, 69, 119, 89, 72, 10, 75, 111, 90, 73, 122, 106, 48, 67, 65, 81, 89, 73, 75, 111, 90, 73,
    122, 106, 48, 68, 65, 81, 99, 68, 81, 103, 65, 69, 55, 66, 67, 65, 79, 99, 113, 103, 115, 80,
    68, 99, 121, 70, 105, 75, 55, 113, 70, 86, 118, 112, 114, 85, 113, 111, 104, 99, 52, 57, 116,
    122, 69, 47, 112, 70, 10, 121, 79, 68, 68, 78, 98, 79, 74, 103, 77, 115, 51, 85, 102, 87, 97,
    114, 69, 66, 82, 47, 111, 101, 49, 83, 111, 120, 81, 108, 99, 121, 70, 82, 101, 67, 47, 57, 87,
    117, 107, 67, 118, 49, 85, 80, 43, 99, 88, 119, 97, 77, 102, 77, 66, 48, 119, 71, 119, 89, 68,
    86, 82, 48, 82, 10, 66, 66, 81, 119, 69, 111, 73, 81, 101, 85, 57, 76, 97, 122, 90, 84, 77,
    107, 70, 87, 97, 70, 108, 120, 86, 106, 86, 70, 89, 84, 65, 75, 66, 103, 103, 113, 104, 107,
    106, 79, 80, 81, 81, 68, 65, 103, 78, 74, 65, 68, 66, 71, 65, 105, 69, 65, 119, 65, 109, 109,
    47, 114, 103, 112, 10, 84, 80, 48, 57, 88, 77, 102, 83, 49, 118, 70, 79, 84, 65, 48, 122, 79,
    66, 75, 103, 53, 97, 56, 111, 86, 106, 83, 111, 89, 67, 48, 80, 83, 103, 52, 67, 73, 81, 68,
    54, 73, 121, 73, 115, 56, 76, 111, 117, 106, 109, 82, 102, 78, 102, 53, 115, 57, 106, 97, 121,
    72, 102, 107, 112, 10, 80, 67, 106, 106, 111, 104, 68, 112, 114, 122, 49, 67, 78, 75, 79, 66,
    53, 81, 61, 61, 10, 45, 45, 45, 45, 45, 69, 78, 68, 32, 67, 69, 82, 84, 73, 70, 73, 67, 65, 84,
    69, 45, 45, 45, 45, 45, 10,
];

#[derive(Debug, Parser)]
#[clap(name = "universal connectivity rust peer")]
struct Opt {
    /// Address to listen on.
    #[clap(long)]
    listen_address: Option<String>,

    /// Address of a remote peer to connect to.
    #[clap(long)]
    remote_address: Option<Multiaddr>,
}

/// An example WebRTC peer that will accept connections
#[tokio::main]
async fn main() -> Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let opt = Opt::parse();

    let mut swarm = create_swarm()?;

    swarm.listen_on(format!("/ip4/0.0.0.0/udp/9090/webrtc-direct").parse()?)?;

    if let Some(listen_address) = opt.listen_address {
        swarm.add_external_address(
            format!("/ip4/{}/udp/9090/webrtc-direct", listen_address).parse()?,
            AddressScore::Infinite,
        );
    }

    if let Some(remote_address) = opt.remote_address {
        swarm.dial(remote_address).unwrap();
    }

    let mut tick = futures_timer::Delay::new(TICK_INTERVAL);

    let now = Instant::now();
    loop {
        match futures::future::select(swarm.next(), &mut tick).await {
            futures::future::Either::Left((event, _)) => match event.unwrap() {
                SwarmEvent::NewListenAddr { address, .. } => {
                    let p2p_address = address.with(Protocol::P2p((*swarm.local_peer_id()).into()));
                    info!("Listen p2p address: {p2p_address:?}");
                    swarm.add_external_address(p2p_address, AddressScore::Infinite);
                }
                SwarmEvent::ConnectionEstablished { peer_id, .. } => {
                    info!("Connected to {peer_id}");
                }
                SwarmEvent::OutgoingConnectionError { peer_id, error } => {
                    warn!("Failed to dial {peer_id:?}: {error}");
                }
                SwarmEvent::ConnectionClosed { peer_id, cause, .. } => {
                    warn!("Connection to {peer_id} closed: {cause:?}");
                }
                SwarmEvent::Behaviour(BehaviourEvent::Relay(e)) => {
                    debug!("{:?}", e);
                }
                SwarmEvent::Behaviour(BehaviourEvent::Gossipsub(
                    libp2p::gossipsub::Event::Message {
                        message_id: _,
                        propagation_source: _,
                        message,
                    },
                )) => {
                    debug!(
                        "Received message from {:?}: {}",
                        message.source,
                        String::from_utf8(message.data).unwrap()
                    );
                }
                SwarmEvent::Behaviour(BehaviourEvent::Gossipsub(
                    libp2p::gossipsub::Event::Subscribed { peer_id, topic },
                )) => {
                    debug!("{peer_id} subscribed to {topic}");
                }
                SwarmEvent::Behaviour(BehaviourEvent::Identify(e)) => {
                    info!("BehaviourEvent::Identify {:?}", e);

                    if let identify::Event::Received {
                        peer_id,
                        info:
                            identify::Info {
                                listen_addrs,
                                protocols,
                                observed_addr,
                                ..
                            },
                    } = e
                    {
                        debug!("identify::Event::Received observed_addr: {}", observed_addr);

                        swarm.add_external_address(observed_addr, AddressScore::Infinite);

                        if protocols
                            .iter()
                            .any(|p| p.as_bytes() == KADEMLIA_PROTOCOL_NAME)
                        {
                            for addr in listen_addrs {
                                debug!("identify::Event::Received listen addr: {}", addr);
                                // TODO (fixme): the below doesn't work because the address is still missing /webrtc/p2p even after https://github.com/libp2p/js-libp2p-webrtc/pull/121
                                // swarm.behaviour_mut().kademlia.add_address(&peer_id, addr);

                                let webrtc_address = Multiaddr::try_from(
                                    addr.to_string()
                                        + "/webrtc/p2p/"
                                        + &peer_id.clone().to_string(),
                                )?;
                                swarm
                                    .behaviour_mut()
                                    .kademlia
                                    .add_address(&peer_id, webrtc_address);

                                // TODO: below is how we should be constructing the address (not string manipulation)
                                // let webrtc_address = addr.with(Protocol::WebRTC(peer_id.clone().into()));
                            }
                        }
                    }
                }
                SwarmEvent::Behaviour(BehaviourEvent::Kademlia(e)) => {
                    info!("Kademlia event: {:?}", e);
                }
                event => {
                    debug!("Other type of event: {:?}", event);
                }
            },
            futures::future::Either::Right(_) => {
                tick = futures_timer::Delay::new(TICK_INTERVAL);

                info!(
                    "external addrs: {:?}",
                    swarm.external_addresses().collect::<Vec<&AddressRecord>>()
                );

                if let Err(e) = swarm.behaviour_mut().kademlia.bootstrap() {
                    debug!("Failed to run Kademlia bootstrap: {e:?}");
                }

                let message = format!(
                    "Hello world! Sent from the rust-peer at: {:4}s",
                    now.elapsed().as_secs_f64()
                );

                if let Err(err) = swarm.behaviour_mut().gossipsub.publish(
                    gossipsub::IdentTopic::new("universal-connectivity"),
                    message.as_bytes(),
                ) {
                    error!("Failed to publish periodic message: {err}")
                }
            }
        }
    }
}

#[derive(NetworkBehaviour)]
struct Behaviour {
    gossipsub: gossipsub::Behaviour,
    identify: identify::Behaviour,
    kademlia: Kademlia<MemoryStore>,
    keep_alive: keep_alive::Behaviour,
    // ping: ping::Behaviour,
    relay: relay::Behaviour,
}

fn create_swarm() -> Result<Swarm<Behaviour>> {
    let f = File::open("private_key")?;
    let mut reader = BufReader::new(f);
    let mut buffer = Vec::new();

    reader.read_to_end(&mut buffer)?;

    let local_key = identity::Keypair::ed25519_from_bytes(&mut buffer)?;

    let local_peer_id = PeerId::from(local_key.public());
    debug!("Local peer id: {local_peer_id}");

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

    let pem_str = std::str::from_utf8(STATIC_CERTIFICATE).unwrap();

    let transport = webrtc::tokio::Transport::new(
        local_key.clone(),
        webrtc::tokio::Certificate::from_pem(pem_str)?,
    )
    .map(|(local_peer_id, conn), _| (local_peer_id, StreamMuxerBox::new(conn)))
    .boxed();

    let identify_config = identify::Behaviour::new(identify::Config::new(
        "/ipfs/0.1.0".into(),
        local_key.public().clone(),
    ));

    // Create a Kademlia behaviour.
    let mut cfg = KademliaConfig::default();
    cfg.set_protocol_names(vec![Cow::Owned(KADEMLIA_PROTOCOL_NAME.to_vec())]);
    let store = MemoryStore::new(local_peer_id);
    let kad_behaviour = Kademlia::with_config(local_peer_id, store, cfg);

    let behaviour = Behaviour {
        gossipsub,
        identify: identify_config,
        kademlia: kad_behaviour,
        keep_alive: keep_alive::Behaviour::default(),
        // ping: ping::Behaviour::default(),
        relay: relay::Behaviour::new(local_peer_id, Default::default()),
    };
    Ok(SwarmBuilder::with_tokio_executor(transport, behaviour, local_peer_id).build())
}
