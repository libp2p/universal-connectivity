use crate::{Codec as FileExchangeCodec, Message, Options, Request as FileRequest};
use anyhow::Result;
use clap::Parser;
use futures::StreamExt;
use libp2p::{
    core::muxing::StreamMuxerBox,
    gossipsub, identify, identity,
    kad::store::MemoryStore,
    kad::{Behaviour as Kademlia, Config as KademliaConfig},
    memory_connection_limits,
    multiaddr::{Multiaddr, Protocol},
    relay,
    request_response::{self, ProtocolSupport},
    swarm::{NetworkBehaviour, Swarm, SwarmEvent},
    PeerId, StreamProtocol, SwarmBuilder, Transport,
};
use libp2p_webrtc as webrtc;
use libp2p_webrtc::tokio::Certificate;
use std::{
    collections::hash_map::DefaultHasher,
    hash::{Hash, Hasher},
    net::IpAddr,
    time::Duration,
};
use tokio::sync::mpsc::{Receiver, Sender};
use tokio_util::sync::CancellationToken;
use tracing::{debug, error, info, warn};

const KADEMLIA_PROTOCOL_NAME: StreamProtocol = StreamProtocol::new("/ipfs/kad/1.0.0");
const FILE_EXCHANGE_PROTOCOL: StreamProtocol =
    StreamProtocol::new("/universal-connectivity-file/1");
const PORT_WEBRTC: u16 = 9090;
const PORT_QUIC: u16 = 9091;
const GOSSIPSUB_CHAT_TOPIC: &str = "universal-connectivity";
const GOSSIPSUB_CHAT_FILE_TOPIC: &str = "universal-connectivity-file";
const GOSSIPSUB_PEER_DISCOVERY: &str = "universal-connectivity-browser-peer-discovery";
const BOOTSTRAP_NODES: [&str; 4] = [
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt",
];

/// The Peer
pub struct Peer {
    /// The webrtc address
    address_webrtc: Multiaddr,
    /// The quic address
    address_quic: Multiaddr,
    /// The given external addresses
    external_address: Option<IpAddr>,
    /// The multiaddr to dial
    to_dial: Vec<Multiaddr>,
    /// The sender to the ui
    to_ui: Sender<Message>,
    /// The receiver from the ui
    from_ui: Receiver<Message>,
    /// The shutdown token
    shutdown: CancellationToken,
    /// The swarm itself
    swarm: Swarm<Behaviour>,
}

impl Peer {
    /// Create a new Peer instance
    pub async fn new(
        local_key: identity::Keypair,
        webrtc_cert: Certificate,
        to_ui: Sender<Message>,
        from_ui: Receiver<Message>,
        shutdown: CancellationToken,
    ) -> Result<Self> {
        // parse the command line arguments
        let opt = Options::parse();

        let address_webrtc = Multiaddr::from(opt.listen_address)
            .with(Protocol::Udp(PORT_WEBRTC))
            .with(Protocol::WebRTCDirect);

        let address_quic = Multiaddr::from(opt.listen_address)
            .with(Protocol::Udp(PORT_QUIC))
            .with(Protocol::QuicV1);

        let external_address = opt.external_address;

        let to_dial = opt.connect;

        let swarm = {
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

            // Create/subscribe Gossipsub topics
            gossipsub.subscribe(&gossipsub::IdentTopic::new(GOSSIPSUB_CHAT_TOPIC))?;
            gossipsub.subscribe(&gossipsub::IdentTopic::new(GOSSIPSUB_CHAT_FILE_TOPIC))?;
            gossipsub.subscribe(&gossipsub::IdentTopic::new(GOSSIPSUB_PEER_DISCOVERY))?;

            //TODO: double check this protocol string to make sure it is corect
            let identify_config = identify::Behaviour::new(
                identify::Config::new("/ipfs/0.1.0".into(), local_key.public())
                    .with_interval(Duration::from_secs(60)), // do this so we can get timeouts for dropped WebRTC connections
            );

            // Create a Kademlia behaviour.
            // TODO: set the bootstrap timeout interval
            let cfg = KademliaConfig::new(KADEMLIA_PROTOCOL_NAME);
            let store = MemoryStore::new(local_peer_id);
            let kad_behaviour = Kademlia::with_config(local_peer_id, store, cfg);

            let behaviour = Behaviour {
                gossipsub,
                identify: identify_config,
                kademlia: kad_behaviour,
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
                request_response: request_response::Behaviour::new(
                    [(FILE_EXCHANGE_PROTOCOL, ProtocolSupport::Full)],
                    request_response::Config::default(),
                ),
                connection_limits: memory_connection_limits::Behaviour::with_max_percentage(0.9),
            };
            SwarmBuilder::with_existing_identity(local_key.clone())
                .with_tokio()
                .with_quic()
                .with_other_transport(|id_keys| {
                    Ok(
                        webrtc::tokio::Transport::new(id_keys.clone(), webrtc_cert.clone())
                            .map(|(peer_id, conn), _| (peer_id, StreamMuxerBox::new(conn))),
                    )
                })?
                .with_dns()?
                .with_behaviour(|_key| behaviour)?
                .build()
        };

        Ok(Self {
            address_webrtc,
            address_quic,
            external_address,
            to_dial,
            to_ui,
            from_ui,
            shutdown,
            swarm,
        })
    }

    /// Run the Peer
    pub async fn run(&mut self) -> Result<()> {
        self.swarm
            .listen_on(self.address_webrtc.clone())
            .expect("listen on webrtc");
        self.swarm
            .listen_on(self.address_quic.clone())
            .expect("listen on quic");

        for addr in &self.to_dial {
            if let Err(e) = self.swarm.dial(addr.clone()) {
                debug!("Failed to dial {addr}: {e}");
            }
        }

        for peer in &BOOTSTRAP_NODES {
            let multiaddr: Multiaddr = peer.parse().expect("Failed to parse Multiaddr");
            if let Err(e) = self.swarm.dial(multiaddr) {
                debug!("Failed to dial {peer}: {e}");
            }
        }

        let chat_topic_hash = gossipsub::IdentTopic::new(GOSSIPSUB_CHAT_TOPIC).hash();
        let file_topic_hash = gossipsub::IdentTopic::new(GOSSIPSUB_CHAT_FILE_TOPIC).hash();
        let peer_discovery_hash = gossipsub::IdentTopic::new(GOSSIPSUB_PEER_DISCOVERY).hash();

        loop {
            tokio::select! {
                _ = self.shutdown.cancelled() => {
                    break;
                }
                Some(_message) = self.from_ui.recv() => {
                    todo!("Handle UI messages");
                }
                Some(event) = self.swarm.next() => match event {
                    SwarmEvent::NewListenAddr { address, .. } => {
                        if let Some(external_ip) = self.external_address {
                            let external_address = address
                                .replace(0, |_| Some(external_ip.into()))
                                .expect("address.len > 1 and we always return `Some`");

                            self.swarm.add_external_address(external_address);
                        }

                        let p2p_address = address.with(Protocol::P2p(*self.swarm.local_peer_id()));
                        info!("Listening on {p2p_address}");
                    }
                    SwarmEvent::ConnectionEstablished { peer_id, .. } => {
                        info!("Connected to {peer_id}");
                    }
                    SwarmEvent::OutgoingConnectionError { peer_id, error, .. } => {
                        warn!("Failed to dial {peer_id:?}: {error}");
                    }
                    SwarmEvent::IncomingConnectionError { error, .. } => {
                        warn!("{:#}", anyhow::Error::from(error))
                    }
                    SwarmEvent::ConnectionClosed { peer_id, cause, .. } => {
                        warn!("Connection to {peer_id} closed: {cause:?}");
                        self.swarm.behaviour_mut().kademlia.remove_peer(&peer_id);
                        info!("Removed {peer_id} from the routing table (if it was in there).");
                    }
                    SwarmEvent::Behaviour(BehaviourEvent::Relay(e)) => {
                        debug!("{:?}", e);
                    }
                    SwarmEvent::Behaviour(BehaviourEvent::Gossipsub(
                        gossipsub::Event::Message {
                            message_id: _,
                            propagation_source: _,
                            message,
                        },
                    )) => {
                        if message.topic == chat_topic_hash {
                            info!(
                                "Received message from {:?}: {}",
                                message.source,
                                String::from_utf8(message.data).unwrap()
                            );
                            continue;
                        }

                        if message.topic == file_topic_hash {
                            let file_id = String::from_utf8(message.data).unwrap();
                            info!("Received file {} from {:?}", file_id, message.source);

                            let request_id =
                                self.swarm.behaviour_mut().request_response.send_request(
                                    &message.source.unwrap(),
                                    FileRequest {
                                        file_id: file_id.clone(),
                                    },
                                );
                            info!(
                                "Requested file {} to {:?}: req_id:{:?}",
                                file_id, message.source, request_id
                            );
                            continue;
                        }

                        if message.topic == peer_discovery_hash {
                            info!("Received peer discovery from {:?}", message.source);
                            continue;
                        }

                        error!("Unexpected gossipsub topic hash: {:?}", message.topic);
                    }
                    SwarmEvent::Behaviour(BehaviourEvent::Gossipsub(
                        gossipsub::Event::Subscribed { peer_id, topic },
                    )) => {
                        debug!("{peer_id} subscribed to {topic}");
                    }
                    SwarmEvent::Behaviour(BehaviourEvent::Identify(e)) => {
                        info!("BehaviourEvent::Identify {:?}", e);

                        if let identify::Event::Error { peer_id, error, .. } = e {
                            match error {
                                libp2p::swarm::StreamUpgradeError::Timeout => {
                                    // When a browser tab closes, we don't get a swarm event
                                    // maybe there's a way to get this with TransportEvent
                                    // but for now remove the peer from routing table if there's an Identify timeout
                                    self.swarm.behaviour_mut().kademlia.remove_peer(&peer_id);
                                    info!("Removed {peer_id} from the routing table (if it was in there).");
                                }
                                _ => {
                                    debug!("{error}");
                                }
                            }
                        } else if let identify::Event::Received {
                            info: identify::Info { observed_addr, .. },
                            ..
                        } = e
                        {
                            debug!("identify::Event::Received observed_addr: {}", observed_addr);

                            // this should switch us from client to server mode in kademlia
                            self.swarm.add_external_address(observed_addr);
                        }
                    }
                    SwarmEvent::Behaviour(BehaviourEvent::Kademlia(e)) => {
                        debug!("Kademlia event: {:?}", e);
                    }
                    SwarmEvent::Behaviour(BehaviourEvent::RequestResponse(
                        request_response::Event::Message { message, .. },
                    )) => match message {
                        request_response::Message::Request { request, .. } => {
                            //TODO: support ProtocolSupport::Full
                            debug!(
                                "umimplemented: request_response::Message::Request: {:?}",
                                request
                            );
                        }
                        request_response::Message::Response { response, .. } => {
                            info!(
                                "request_response::Message::Response: size:{}",
                                response.file_body.len()
                            );
                            // TODO: store this file (in memory or disk) and provider it via Kademlia
                        }
                    },
                    SwarmEvent::Behaviour(BehaviourEvent::RequestResponse(
                        request_response::Event::OutboundFailure {
                            request_id, error, ..
                        },
                    )) => {
                        error!(
                            "request_response::Event::OutboundFailure for request {:?}: {:?}",
                            request_id, error
                        );
                    }
                    event => {
                        debug!("Other type of event: {:?}", event);
                    }
                }
            }
        }

        Ok(())
    }
}

#[derive(NetworkBehaviour)]
struct Behaviour {
    gossipsub: gossipsub::Behaviour,
    identify: identify::Behaviour,
    kademlia: Kademlia<MemoryStore>,
    relay: relay::Behaviour,
    request_response: request_response::Behaviour<FileExchangeCodec>,
    connection_limits: memory_connection_limits::Behaviour,
}
