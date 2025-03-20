use crate::{Codec as FileExchangeCodec, Message, Options, Request as FileRequest};
use anyhow::Result;
use clap::Parser;
use futures::StreamExt;
use libp2p::{
    core::muxing::StreamMuxerBox,
    gossipsub::{
        self, Behaviour as Gossipsub, Event as GossipsubEvent, IdentTopic as GossipsubIdentTopic,
        Message as GossipsubMessage, MessageId as GossipsubMessageId,
    },
    identify::{Behaviour as Identify, Config as IdentifyConfig, Event as IdentifyEvent},
    identity,
    kad::store::MemoryStore,
    kad::{Behaviour as Kademlia, Config as KademliaConfig},
    memory_connection_limits::Behaviour as MemoryConnectionLimits,
    multiaddr::{Multiaddr, Protocol},
    noise,
    relay::{Behaviour as Relay, Config as RelayConfig},
    request_response::{
        Behaviour as RequestResponse, Config as RequestResponseConfig,
        Event as RequestResponseEvent, Message as RequestResponseMessage, ProtocolSupport,
    },
    swarm::{NetworkBehaviour, Swarm, SwarmEvent},
    tcp, yamux, PeerId, StreamProtocol, SwarmBuilder, Transport,
};
use libp2p_webrtc as webrtc;
use libp2p_webrtc::tokio::Certificate;
use std::{
    collections::hash_map::DefaultHasher,
    hash::{Hash, Hasher},
    time::Duration,
};
use tokio::sync::mpsc::{Receiver, Sender};
use tokio_util::sync::CancellationToken;
use tracing::{debug, error, info, warn};

// Protocol Names
const IPFS_KADEMLIA_PROTOCOL_NAME: StreamProtocol = StreamProtocol::new("/ipfs/kad/1.0.0");
const IPFS_IDENTIFY_PROTOCOL_NAME: StreamProtocol = StreamProtocol::new("/ipfs/id/1.0.0");
const FILE_EXCHANGE_PROTOCOL_NAME: StreamProtocol =
    StreamProtocol::new("/universal-connectivity-file/1");

// Gossipsub Topics
const GOSSIPSUB_CHAT_TOPIC: &str = "universal-connectivity";
const GOSSIPSUB_CHAT_FILE_TOPIC: &str = "universal-connectivity-file";
const GOSSIPSUB_PEER_DISCOVERY: &str = "universal-connectivity-browser-peer-discovery";

// Listen Ports
const PORT_WEBRTC: u16 = 9090;
const PORT_QUIC: u16 = 9091;
const PORT_TCP: u16 = 9092;

// Bootstrap Nodes
const BOOTSTRAP_NODES: [&str; 4] = [
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt",
];

/// The Peer Behaviour
#[derive(NetworkBehaviour)]
struct Behaviour {
    gossipsub: Gossipsub,
    identify: Identify,
    kademlia: Kademlia<MemoryStore>,
    relay: Relay,
    request_response: RequestResponse<FileExchangeCodec>,
    connection_limits: MemoryConnectionLimits,
}

/// The Peer state
pub struct Peer {
    /// The webrtc address we listen on
    address_webrtc: Multiaddr,
    /// The quic address we listen on
    address_quic: Multiaddr,
    /// The tcp address we listen on
    address_tcp: Multiaddr,
    /// The external addresses that others see, given on command line
    external_address: Option<Multiaddr>,
    /// The multiaddrs to dial, given on command line
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
    /// Create a new Peer instance by initializing the swarm and peer state
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

        let address_tcp = Multiaddr::from(opt.listen_address).with(Protocol::Tcp(PORT_TCP));

        let external_address = opt.external_address.map(Multiaddr::from);

        let to_dial = opt.connect;

        // initialize the swarm
        let swarm = {
            let local_peer_id = PeerId::from(local_key.public());
            debug!("Local peer id: {local_peer_id}");

            // Create a gossipsub behaviour
            let gossipsub = {
                // This closure creates a unique message id for each message by hashing its contents
                let message_id_fn = |message: &GossipsubMessage| {
                    let mut s = DefaultHasher::new();
                    message.data.hash(&mut s);
                    GossipsubMessageId::from(s.finish().to_string())
                };

                // Set a custom gossipsub configuration
                let gossipsub_config = gossipsub::ConfigBuilder::default()
                    // This sets the kind of message validation. The default is Strict (enforce message signing)
                    .validation_mode(gossipsub::ValidationMode::Permissive)
                    // This ensures no two messages of the same content will be propagated.
                    .message_id_fn(message_id_fn)
                    .mesh_outbound_min(1)
                    .mesh_n_low(1)
                    .flood_publish(true)
                    .build()
                    .expect("Valid config");

                // build a gossipsub network behaviour
                Gossipsub::new(
                    gossipsub::MessageAuthenticity::Signed(local_key.clone()),
                    gossipsub_config,
                )
                .expect("Correct configuration")
            };

            // Create an Identify behaviour
            let identify = {
                let cfg = IdentifyConfig::new(
                    IPFS_IDENTIFY_PROTOCOL_NAME.to_string(), // bug: https://github.com/libp2p/rust-libp2p/issues/5940
                    local_key.public(),
                );
                Identify::new(cfg)
            };

            // Create a Kademlia behaviour
            let kademlia = {
                let mut cfg = KademliaConfig::new(IPFS_KADEMLIA_PROTOCOL_NAME);
                cfg.set_query_timeout(Duration::from_secs(60));
                let store = MemoryStore::new(local_peer_id);
                Kademlia::with_config(local_peer_id, store, cfg)
            };

            // Create the Relay behaviour
            let relay = {
                let cfg = RelayConfig {
                    max_reservations: usize::MAX,
                    max_reservations_per_peer: 100,
                    reservation_rate_limiters: Vec::default(),
                    circuit_src_rate_limiters: Vec::default(),
                    max_circuits: usize::MAX,
                    max_circuits_per_peer: 100,
                    ..Default::default()
                };
                Relay::new(local_peer_id, cfg)
            };

            // Create the RequestResponse behaviour
            let request_response = {
                let cfg = RequestResponseConfig::default();
                RequestResponse::new([(FILE_EXCHANGE_PROTOCOL_NAME, ProtocolSupport::Full)], cfg)
            };

            // Create the ConnectionLimits behaviour
            let connection_limits = MemoryConnectionLimits::with_max_percentage(0.9);

            // Initialize the overall peer behaviour
            let behaviour = Behaviour {
                gossipsub,
                identify,
                kademlia,
                relay,
                request_response,
                connection_limits,
            };

            // Build the swarm
            SwarmBuilder::with_existing_identity(local_key.clone())
                .with_tokio()
                .with_tcp(
                    tcp::Config::default(),
                    noise::Config::new,
                    yamux::Config::default,
                )?
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
            address_tcp,
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
        // Listen on the given addresses
        if let Err(e) = self.swarm.listen_on(self.address_webrtc.clone()) {
            self.to_ui
                .send(Message::Event(format!("Failed to listen on webrtc: {e}")))
                .await?;
        }
        if let Err(e) = self.swarm.listen_on(self.address_quic.clone()) {
            self.to_ui
                .send(Message::Event(format!("Failed to listen on quic: {e}")))
                .await?;
        }
        if let Err(e) = self.swarm.listen_on(self.address_tcp.clone()) {
            self.to_ui
                .send(Message::Event(format!("Failed to listen on tcp: {e}")))
                .await?;
        }

        // Dial the given addresses
        for addr in &self.to_dial {
            if let Err(e) = self.swarm.dial(addr.clone()) {
                debug!("Failed to dial {addr}: {e}");
            }
        }

        // Dial the bootstrap nodes
        for peer in &BOOTSTRAP_NODES {
            let multiaddr: Multiaddr = peer.parse().expect("Failed to parse Multiaddr");
            if let Err(e) = self.swarm.dial(multiaddr) {
                debug!("Failed to dial {peer}: {e}");
            }
        }

        // Initialize the gossipsub topics and hashes
        let chat_topic = GossipsubIdentTopic::new(GOSSIPSUB_CHAT_TOPIC);
        let file_topic = GossipsubIdentTopic::new(GOSSIPSUB_CHAT_FILE_TOPIC);
        let peer_discovery = GossipsubIdentTopic::new(GOSSIPSUB_PEER_DISCOVERY);
        let chat_topic_hash = chat_topic.hash();
        let file_topic_hash = file_topic.hash();
        let peer_discovery_hash = peer_discovery.hash();

        // Subscribe to the gossipsub topics
        for topic in &[chat_topic, file_topic, peer_discovery] {
            if let Err(e) = self.swarm.behaviour_mut().gossipsub.subscribe(topic) {
                debug!("Failed to subscribe to topic {topic}: {e}");
            }
        }

        // Run the main loop
        loop {
            tokio::select! {
                _ = self.shutdown.cancelled() => {
                    info!("Shutting down the peer");
                    break;
                }

                Some(message) = self.from_ui.recv() => {
                    match message {
                        Message::Chat { data, .. } => {
                            if let Err(e) = self.swarm.behaviour_mut().gossipsub.publish(chat_topic_hash.clone(), data) {
                                debug!("Failed to publish chat message: {e}");
                            }
                        }
                        Message::AllPeers { .. } => {
                            let peers = self.swarm.behaviour().gossipsub.all_peers().map(|(peer_id, topics)| {
                                (peer_id.clone(), topics.iter().map(|t| t.to_string()).collect())
                            }).collect();
                            self.to_ui.send(Message::AllPeers { peers }).await?;
                        }
                        _ => {
                            debug!("Unhandled message: {:?}", message);
                        }
                    }
                }

                Some(event) = self.swarm.next() => match event {

                    // When we figure out what our external address is
                    SwarmEvent::NewListenAddr { address, .. } => {
                        if self.update_external_address(&address).await? {
                            let p2p_address = address
                                .clone()
                                .with(Protocol::P2p(*self.swarm.local_peer_id()));
                            self.to_ui
                                .send(Message::Event(format!("Listening on {p2p_address}")))
                                .await?;
                        }
                    }

                    // When we successfully connect to a peer
                    SwarmEvent::ConnectionEstablished { peer_id, .. } => {
                        info!("Connected to {peer_id}");
                    }

                    // When we fail to connect to a peer
                    SwarmEvent::OutgoingConnectionError { peer_id, error, .. } => {
                        warn!("Failed to dial {peer_id:?}: {error}");
                    }

                    // When we fail to accept a connection from a peer
                    SwarmEvent::IncomingConnectionError { error, .. } => {
                        warn!("{:#}", anyhow::Error::from(error))
                    }

                    // When a connection to a peer is closed
                    SwarmEvent::ConnectionClosed { peer_id, cause, .. } => {
                        warn!("Connection to {peer_id} closed: {cause:?}");
                        self.swarm.behaviour_mut().kademlia.remove_peer(&peer_id);
                        info!("Removed {peer_id} from the routing table (if it was in there).");
                    }

                    // When we receive a relay event
                    SwarmEvent::Behaviour(BehaviourEvent::Relay(event)) => {
                        //TODO: add proper relaying behavour
                        debug!("{:?}", event);
                    }

                    // When we receive a gossipsub event
                    SwarmEvent::Behaviour(BehaviourEvent::Gossipsub(event)) => match event {
                        GossipsubEvent::Message { message, .. } => match message {
                            GossipsubMessage { source, data, .. } if message.topic == chat_topic_hash => {
                                self.to_ui.send(Message::Event(format!("Received chat message from {:?}", source))).await?;
                                self.to_ui.send(Message::Chat {
                                    source,
                                    data,
                                }).await?;
                            }
                            GossipsubMessage { source, data, .. } if message.topic == file_topic_hash => {
                                let file_id = String::from_utf8(data).unwrap();
                                info!("Received file {file_id} from {:?}", source);

                                if let Some(source) = source {
                                    let request_id = self.swarm.behaviour_mut().request_response.send_request(
                                        &source,
                                        FileRequest {
                                            file_id: file_id.clone(),
                                        },
                                    );
                                    info!(
                                        "Requested file {file_id} to {:?}: req_id:{:?}", source, request_id
                                    );
                                } else {
                                    warn!("Received file id {file_id} from an unknown source");
                                }
                            }
                            message if message.topic == peer_discovery_hash => {
                                self.to_ui.send(Message::Event(format!("Received peer discovery: {:?}", message))).await?;
                            }
                            GossipsubMessage { topic, .. } => {
                                self.to_ui.send(Message::Event(format!("Unknown topic {:?}", topic))).await?;
                                warn!("Received message from an unknown topic: {:?}", topic);
                            }
                        }
                        GossipsubEvent::Subscribed { peer_id, topic } => {
                            debug!("{peer_id} subscribed to {topic}");
                            if topic == chat_topic_hash {
                                self.to_ui.send(Message::AddPeer(peer_id)).await?;
                            }
                        }
                        GossipsubEvent::Unsubscribed { peer_id, topic } => {
                            debug!("{peer_id} unsubscribed from {topic}");
                            if topic == chat_topic_hash {
                                self.to_ui.send(Message::RemovePeer(peer_id)).await?;
                            }
                        }
                        GossipsubEvent::GossipsubNotSupported { peer_id } => {
                            warn!("{peer_id} does not support gossipsub");
                        }
                        GossipsubEvent::SlowPeer { peer_id, .. } => {
                            warn!("{peer_id} is a slow peer");
                        }
                    }

                    // When we receive an identify event
                    SwarmEvent::Behaviour(BehaviourEvent::Identify(event)) => match event {
                        IdentifyEvent::Received { info, .. } => {
                            self.update_external_address(&info.observed_addr).await?;
                        }
                        IdentifyEvent::Sent { .. } => {
                            debug!("identify::Event::Sent");
                        }
                        IdentifyEvent::Pushed { .. } => {
                            debug!("identify::Event::Pushed");
                        }
                        IdentifyEvent::Error { peer_id, error, .. } => {
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
                        }
                    }

                    // When we receive a kademlia event
                    SwarmEvent::Behaviour(BehaviourEvent::Kademlia(e)) => {
                        //TODO: proper kademlia event handling
                        debug!("Kademlia event: {:?}", e);
                    }

                    // When we receive a request_response event
                    SwarmEvent::Behaviour(BehaviourEvent::RequestResponse(
                        RequestResponseEvent::Message { message, .. },
                    )) => match message {
                        RequestResponseMessage::Request { request, .. } => {
                            //TODO: support ProtocolSupport::Full
                            debug!(
                                "umimplemented: request_response::Message::Request: {:?}",
                                request
                            );
                        }
                        RequestResponseMessage::Response { response, .. } => {
                            info!(
                                "request_response::Message::Response: size:{}",
                                response.file_body.len()
                            );
                            // TODO: store this file (in memory or disk) and provider it via Kademlia
                        }
                    },
                    SwarmEvent::Behaviour(BehaviourEvent::RequestResponse(
                        RequestResponseEvent::OutboundFailure {
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

    /// Update our external address if needed
    pub async fn update_external_address(&mut self, address: &Multiaddr) -> Result<bool> {
        if let Some(addr) = &self.external_address {
            if *addr != *address {
                self.swarm.add_external_address(address.clone());
                self.external_address = Some(address.clone());
                Ok(true)
            } else {
                info!("External address already set");
                Ok(false)
            }
        } else {
            self.swarm.add_external_address(address.clone());
            self.external_address = Some(address.clone());
            Ok(true)
        }
    }
}
