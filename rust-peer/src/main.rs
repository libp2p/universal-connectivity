use anyhow::{Context, Result};
use clap::Parser;
use futures::future::{select, Either};
use futures::StreamExt;
use libp2p::{
    core::muxing::StreamMuxerBox,
    gossipsub, identify, identity,
    kad::record::store::MemoryStore,
    kad::{Kademlia, KademliaConfig},
    multiaddr::{Multiaddr, Protocol},
    relay,
    swarm::{
        keep_alive, AddressRecord, AddressScore, NetworkBehaviour, Swarm, SwarmBuilder, SwarmEvent,
    },
    PeerId, Transport,
};
use libp2p_quic as quic;
use libp2p_webrtc as webrtc;
use libp2p_webrtc::tokio::Certificate;
use log::{debug, error, info, warn};
use std::net::{IpAddr, Ipv4Addr};
use std::path::Path;
use std::{
    borrow::Cow,
    collections::hash_map::DefaultHasher,
    hash::{Hash, Hasher},
    time::{Duration, Instant},
};
use tokio::fs;

const TICK_INTERVAL: Duration = Duration::from_secs(15);
const KADEMLIA_PROTOCOL_NAME: &[u8] = b"/universal-connectivity/lan/kad/1.0.0";
const PORT_WEBRTC: u16 = 9090;
const PORT_QUIC: u16 = 9091;
const LOCAL_KEY_PATH: &str = "./local_key";
const LOCAL_CERT_PATH: &str = "./cert.pem";

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
    let local_key = read_or_create_identity(Path::new(LOCAL_KEY_PATH))
        .await
        .context("Failed to read identity")?;
    let webrtc_cert = read_or_create_certificate(Path::new(LOCAL_CERT_PATH))
        .await
        .context("Failed to read certificate")?;

    let mut swarm = create_swarm(local_key, webrtc_cert)?;

    let address_webrtc = Multiaddr::from(Ipv4Addr::UNSPECIFIED)
        .with(Protocol::Udp(PORT_WEBRTC))
        .with(Protocol::WebRTCDirect);

    let address_quic = Multiaddr::from(Ipv4Addr::UNSPECIFIED)
        .with(Protocol::Udp(PORT_QUIC))
        .with(Protocol::QuicV1);

    swarm
        .listen_on(address_webrtc.clone())
        .expect("listen on webrtc");
    swarm
        .listen_on(address_quic.clone())
        .expect("listen on quic");

    if let Some(listen_address) = opt.listen_address {
        // match on whether the listen address string is an IP address or not (do nothing if not)
        match listen_address.parse::<IpAddr>() {
            Ok(ip) => {
                let opt_address_webrtc = Multiaddr::from(ip)
                    .with(Protocol::Udp(PORT_WEBRTC))
                    .with(Protocol::WebRTCDirect);
                swarm.add_external_address(opt_address_webrtc, AddressScore::Infinite);
            }
            Err(_) => {
                debug!(
                    "listen_address provided is not an IP address: {}",
                    listen_address
                )
            }
        }
    }

    if let Some(remote_address) = opt.remote_address {
        swarm
            .dial(remote_address)
            .expect("a valid remote address to be provided");
    }

    let mut tick = futures_timer::Delay::new(TICK_INTERVAL);

    let now = Instant::now();
    loop {
        match select(swarm.next(), &mut tick).await {
            Either::Left((event, _)) => match event.unwrap() {
                SwarmEvent::NewListenAddr { address, .. } => {
                    let p2p_address = address.with(Protocol::P2p((*swarm.local_peer_id()).into()));
                    info!("Listen p2p address: {p2p_address:?}");
                }
                SwarmEvent::ConnectionEstablished { peer_id, .. } => {
                    info!("Connected to {peer_id}");
                }
                SwarmEvent::OutgoingConnectionError { peer_id, error } => {
                    warn!("Failed to dial {peer_id:?}: {error}");
                }
                SwarmEvent::ConnectionClosed { peer_id, cause, .. } => {
                    warn!("Connection to {peer_id} closed: {cause:?}");
                    swarm.behaviour_mut().kademlia.remove_peer(&peer_id);
                    info!("Removed {peer_id} from the routing table (if it was in there).");
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
                    info!(
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

                    if let identify::Event::Error { peer_id, error } = e {
                        match error {
                            libp2p::swarm::ConnectionHandlerUpgrErr::Timeout => {
                                // When a browser tab closes, we don't get a swarm event
                                // maybe there's a way to get this with TransportEvent
                                // but for now remove the peer from routing table if there's an Identify timeout
                                swarm.behaviour_mut().kademlia.remove_peer(&peer_id);
                                info!("Removed {peer_id} from the routing table (if it was in there).");
                            }
                            _ => {
                                debug!("{error}");
                            }
                        }
                    } else if let identify::Event::Received {
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

                                let webrtc_address = addr
                                    .with(Protocol::WebRTC)
                                    .with(Protocol::P2p(peer_id.into()));

                                swarm
                                    .behaviour_mut()
                                    .kademlia
                                    .add_address(&peer_id, webrtc_address.clone());
                                info!("Added {webrtc_address} to the routing table.");
                            }
                        }
                    }
                }
                SwarmEvent::Behaviour(BehaviourEvent::Kademlia(e)) => {
                    debug!("Kademlia event: {:?}", e);
                }
                event => {
                    debug!("Other type of event: {:?}", event);
                }
            },
            Either::Right(_) => {
                tick = futures_timer::Delay::new(TICK_INTERVAL);

                debug!(
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
    relay: relay::Behaviour,
}

fn create_swarm(
    local_key: identity::Keypair,
    certificate: Certificate,
) -> Result<Swarm<Behaviour>> {
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

    let transport = {
        let webrtc = webrtc::tokio::Transport::new(local_key.clone(), certificate);

        let quic = quic::tokio::Transport::new(quic::Config::new(&local_key));

        webrtc
            .or_transport(quic)
            .map(|fut, _| match fut {
                futures::future::Either::Right((local_peer_id, conn)) => {
                    (local_peer_id, StreamMuxerBox::new(conn))
                }
                futures::future::Either::Left((local_peer_id, conn)) => {
                    (local_peer_id, StreamMuxerBox::new(conn))
                }
            })
            .boxed()
    };

    let identify_config = identify::Behaviour::new(
        identify::Config::new("/ipfs/0.1.0".into(), local_key.public())
            .with_interval(Duration::from_secs(60)), // do this so we can get timeouts for dropped WebRTC connections
    );

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
        relay: relay::Behaviour::new(
            local_peer_id,
            relay::Config {
                max_reservations: usize::MAX,
                max_reservations_per_peer: 100,
                reservation_rate_limiters: Vec::default(),
                circuit_src_rate_limiters: Vec::default(),
                max_circuits: usize::MAX,
                max_circuits_per_peer: 100,
                ..Default::default()
            },
        ),
    };
    Ok(SwarmBuilder::with_tokio_executor(transport, behaviour, local_peer_id).build())
}

async fn read_or_create_certificate(path: &Path) -> Result<Certificate> {
    if path.exists() {
        let pem = fs::read_to_string(&path).await?;

        info!("Using existing certificate from {}", path.display());

        return Ok(Certificate::from_pem(&pem)?);
    }

    let cert = Certificate::generate(&mut rand::thread_rng())?;
    fs::write(&path, &cert.serialize_pem().as_bytes()).await?;

    info!(
        "Generated new certificate and wrote it to {}",
        path.display()
    );

    Ok(cert)
}

async fn read_or_create_identity(path: &Path) -> Result<identity::Keypair> {
    if path.exists() {
        let bytes = fs::read(&path).await?;

        info!("Using existing identity from {}", path.display());

        return Ok(identity::Keypair::from_protobuf_encoding(&bytes)?); // This only works for ed25519 but that is what we are using.
    }

    let identity = identity::Keypair::generate_ed25519();

    fs::write(&path, &identity.to_protobuf_encoding()?).await?;

    info!("Generated new identity and wrote it to {}", path.display());

    Ok(identity)
}
