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
use rand::thread_rng;
use std::time::Instant;
use std::{
    borrow::Cow,
    hash::{Hash, Hasher},
};
use std::{collections::hash_map::DefaultHasher, time::Duration};

// TODO: replace with our private bootstrap node
// const BOOTNODES: [&str; 4] = [
//     "QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
//     "QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
//     "QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb",
//     "QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt",
// ];

const TICK_INTERVAL: Duration = Duration::from_secs(5);
const KADEMLIA_PROTOCOL_NAME: &'static [u8] = b"/universal-connectivity/lan/kad/1.0.0";

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
                // SwarmEvent::OutgoingConnectionError { peer_id, error } => {
                //     warn!("Failed to dial {peer_id:?}: {error}");
                // }
                // SwarmEvent::ConnectionClosed { peer_id, cause, .. } => {
                //     warn!("Connection to {peer_id} closed: {cause:?}");
                // }
                // SwarmEvent::Behaviour(BehaviourEvent::Relay(e)) => {
                //     info!("{:?}", e);
                // }
                // SwarmEvent::Behaviour(BehaviourEvent::Gossipsub(
                //     libp2p::gossipsub::Event::Message {
                //         message_id: _,
                //         propagation_source: _,
                //         message,
                //     },
                // )) => {
                //     info!(
                //         "Received message from {:?}: {}",
                //         message.source,
                //         String::from_utf8(message.data).unwrap()
                //     );
                // }
                // SwarmEvent::Behaviour(BehaviourEvent::Gossipsub(
                //     libp2p::gossipsub::Event::Subscribed { peer_id, topic },
                // )) => {
                //     info!("{peer_id} subscribed to {topic}");
                // }
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
                        info!("identify::Event::Received observed_addr: {}", observed_addr);

                        swarm.add_external_address(observed_addr, AddressScore::Infinite);

                        if protocols
                            .iter()
                            .any(|p| p.as_bytes() == KADEMLIA_PROTOCOL_NAME)
                        {
                            for addr in listen_addrs {
                                info!("identify::Event::Received listen addr: {}", addr);
                                // swarm.behaviour_mut().kademlia.add_address(&peer_id, addr);

                                let webrtc_address = Multiaddr::try_from(addr.to_string() + "/webrtc/p2p/" + &peer_id.clone().to_string())?;

                                swarm.behaviour_mut().kademlia.add_address(&peer_id, webrtc_address);

                                // let webrtc_address = addr.with(Protocol::WebRTC(peer_id.clone().into()));
                                // fails due to:
                                //     --> src/main.rs:130:60
                                //     |
                                // 130 | ...                   let webrtc_address = addr.with(Protocol::WebRTC(peer_id.clone().into()));
                                //     |                                                      ^^^^^^^^^^^^^^^^------------------------
                                //     |                                                      |
                                //     |                                                      call expression requires function
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

                // if let Err(e) = swarm.behaviour_mut().kademlia.bootstrap() {
                //     error!("Failed to run Kademlia bootstrap: {e:?}");
                // }

                // let message = format!("Hello world! Sent at: {:4}s", now.elapsed().as_secs_f64());

                // if let Err(err) = swarm.behaviour_mut().gossipsub.publish(
                //     gossipsub::IdentTopic::new("universal-connectivity"),
                //     message.as_bytes(),
                // ) {
                //     error!("Failed to publish periodic message: {err}")
                // }
            }
        }
    }
}

#[derive(NetworkBehaviour)]
struct Behaviour {
    // gossipsub: gossipsub::Behaviour,
    identify: identify::Behaviour,
    kademlia: Kademlia<MemoryStore>,
    keep_alive: keep_alive::Behaviour,
    // ping: ping::Behaviour,
    relay: relay::Behaviour,
}

fn create_swarm() -> Result<Swarm<Behaviour>> {
    let local_key = identity::Keypair::generate_ed25519();
    let local_peer_id = PeerId::from(local_key.public());
    debug!("Local peer id: {local_peer_id}");

    // // To content-address message, we can take the hash of message and use it as an ID.
    // let message_id_fn = |message: &gossipsub::Message| {
    //     let mut s = DefaultHasher::new();
    //     message.data.hash(&mut s);
    //     gossipsub::MessageId::from(s.finish().to_string())
    // };

    // // Set a custom gossipsub configuration
    // let gossipsub_config = gossipsub::ConfigBuilder::default()
    //     .validation_mode(gossipsub::ValidationMode::Permissive) // This sets the kind of message validation. The default is Strict (enforce message signing)
    //     .message_id_fn(message_id_fn) // content-address messages. No two messages of the same content will be propagated.
    //     .mesh_outbound_min(1)
    //     .mesh_n_low(1)
    //     .flood_publish(true)
    //     .build()
    //     .expect("Valid config");

    // // build a gossipsub network behaviour
    // let mut gossipsub = gossipsub::Behaviour::new(
    //     gossipsub::MessageAuthenticity::Signed(local_key.clone()),
    //     gossipsub_config,
    // )
    // .expect("Correct configuration");

    // // Create a Gossipsub topic
    // let topic = gossipsub::IdentTopic::new("universal-connectivity");

    // // subscribes to our topic
    // gossipsub.subscribe(&topic)?;

    let transport = webrtc::tokio::Transport::new(
        local_key.clone(),
        webrtc::tokio::Certificate::generate(&mut thread_rng())?,
    );

    let identify_config = identify::Behaviour::new(
        identify::Config::new("/ipfs/0.1.0".into(), local_key.public().clone())
    );

    // Create a Kademlia behaviour.
    let mut cfg = KademliaConfig::default();
    cfg.set_protocol_names(vec![Cow::Owned(KADEMLIA_PROTOCOL_NAME.to_vec())]);
    let store = MemoryStore::new(local_peer_id);
    let kad_behaviour = Kademlia::with_config(local_peer_id, store, cfg);

    // Add the bootnodes to the local routing table. `libp2p-dns` built
    // into the `transport` resolves the `dnsaddr` when Kademlia tries
    // to dial these nodes.
    // for peer in &BOOTNODES {
    //     // TODO: update this
    //     kad_behaviour.add_address(&peer.parse()?, "/dnsaddr/bootstrap.libp2p.io".parse()?);
    // }

    let transport = transport
        .map(|(local_peer_id, conn), _| (local_peer_id, StreamMuxerBox::new(conn)))
        .boxed();

    let behaviour = Behaviour {
        // gossipsub,
        identify: identify_config,
        kademlia: kad_behaviour,
        keep_alive: keep_alive::Behaviour::default(),
        // ping: ping::Behaviour::default(),
        relay: relay::Behaviour::new(local_peer_id, Default::default()),
    };
    Ok(SwarmBuilder::with_tokio_executor(transport, behaviour, local_peer_id).build())
}
