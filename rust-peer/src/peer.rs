use crate::{
    decode_unknown_protobuf, ipaddr_to_multiaddr, is_private_ip, pretty_print_fields,
    proto::Peer as DiscoveredPeer, split_peer_id, ChatPeer, Codec as FileExchangeCodec, Message,
    Options, Request as FileRequest,
};
use clap::Parser;
use futures::StreamExt;
use libp2p::{
    autonat::{
        v2::client::{
            Behaviour as AutonatClient, Config as AutonatClientConfig, Event as AutonatClientEvent,
        },
        v2::server::{Behaviour as AutonatServer, Event as AutonatServerEvent},
    },
    connection_limits::{self, Behaviour as ConnectionLimits},
    dcutr::{Behaviour as Dcutr, Event as DcutrEvent},
    gossipsub::{
        self, Behaviour as Gossipsub, Event as GossipsubEvent, IdentTopic as GossipsubIdentTopic,
        Message as GossipsubMessage, MessageId as GossipsubMessageId, TopicHash,
    },
    identify::{Behaviour as Identify, Config as IdentifyConfig, Event as IdentifyEvent},
    identity::{self, PublicKey},
    kad::{
        store::MemoryStore, AddProviderOk, Behaviour as Kademlia, Config as KademliaConfig,
        Event as KademliaEvent, GetClosestPeersOk, GetProvidersOk, QueryId, QueryResult, RecordKey,
    },
    memory_connection_limits::Behaviour as MemoryConnectionLimits,
    multiaddr::{Multiaddr, Protocol},
    noise::Config as NoiseConfig,
    relay::{
        client::{Behaviour as RelayClient, Event as RelayClientEvent},
        Behaviour as RelayServer, Config as RelayServerConfig, Event as RelayServerEvent,
    },
    request_response::{
        Behaviour as RequestResponse, Config as RequestResponseConfig,
        Event as RequestResponseEvent, Message as RequestResponseMessage, ProtocolSupport,
    },
    swarm::{behaviour::toggle::Toggle, NetworkBehaviour, Swarm, SwarmEvent},
    tcp::Config as TcpConfig,
    tls::Config as TlsConfig,
    yamux::Config as YamuxConfig,
    PeerId, StreamProtocol, SwarmBuilder,
};
use libp2p_webrtc as webrtc;
use libp2p_webrtc::tokio::Certificate;
use quick_protobuf::{BytesReader, MessageRead};
use rand_core::OsRng;
use std::{
    collections::{hash_map::DefaultHasher, HashSet},
    fmt::{self, Write},
    hash::{Hash, Hasher},
    time::Duration,
};
use tokio::sync::mpsc::{Receiver, Sender};
use tokio_util::sync::CancellationToken;
use tracing::{debug, error, info, warn};

// Universal connectivity agent string
const UNIVERSAL_CONNECTIVITY_AGENT: &str = "universal-connectivity/0.1.0";

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
const PORT_WEBRTC: u16 = 9090; // UDP
const PORT_QUIC: u16 = 9091; // UDP
const PORT_TCP: u16 = 9092; // TCP

// Kademlia bootstrap interval
const KADEMLIA_BOOTSTRAP_INTERVAL: u64 = 300;
const IPFS_BOOTSTRAP_NODES: [&str; 4] = [
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt",
];

/// The Peer Behaviour
#[derive(NetworkBehaviour)]
struct Behaviour {
    autonat_client: Toggle<AutonatClient>,
    autonat_server: Toggle<AutonatServer>,
    connection_limits: ConnectionLimits,
    dcutr: Toggle<Dcutr>,
    gossipsub: Gossipsub,
    identify: Identify,
    kademlia: Toggle<Kademlia<MemoryStore>>,
    memory_connection_limits: MemoryConnectionLimits,
    relay_client: Toggle<RelayClient>,
    relay_server: Toggle<RelayServer>,
    request_response: RequestResponse<FileExchangeCodec>,
}

// The rust-peer implementation is full featured and supports a number of protocols and transports
// to make it maximally compatible will all other universal connectivity peers
//
// This swarm supports:
// - WebRTC + TLS on port 9090
// - QUIC + Noise on UDP port 9091
// - QUIC + TLS on UDP port 9091
// - TCP + Noise on TCP port 9092
// - TCP + TLS on TCP port 9092

/// The Peer state
pub struct Peer {
    /// The addresses we're listening on
    listen_addresses: HashSet<Multiaddr>,
    /// The external addresses that others see, given on command line
    external_addresses: HashSet<Multiaddr>,
    /// The multiaddrs to dial, given on command line
    to_dial: Vec<String>,
    /// The sender to the ui
    to_ui: Sender<Message>,
    /// The receiver from the ui
    from_ui: Receiver<Message>,
    /// The shutdown token
    shutdown: CancellationToken,
    /// The swarm itself
    swarm: Swarm<Behaviour>,
    /// The query id for the kademlia bootstrap
    bootstrap_query_id: Option<QueryId>,
    /// The query id for providing the universal connectivity agent string
    start_providing_query_id: Option<QueryId>,
    /// The query id for getting the providers of the universal connectivity agent string
    get_providers_query_id: Option<QueryId>,
    /// The query id for getting the closest peers to the universal connectivity agent string
    get_closest_peers_query_id: HashSet<QueryId>,
}

impl Peer {
    /// Create a new Peer instance by initializing the swarm and peer state
    pub async fn new(
        keypair: identity::Keypair,
        tls_cert: Certificate,
        to_ui: Sender<Message>,
        from_ui: Receiver<Message>,
        shutdown: CancellationToken,
    ) -> anyhow::Result<Self> {
        // parse the command line arguments
        let opt = Options::parse();

        // Listen Ports
        // const PORT_WEBRTC: u16 = 9090; // UDP
        // const PORT_QUIC: u16 = 9091; // UDP
        // const PORT_TCP: u16 = 9092; // TCP

        let mut listen_addresses = HashSet::new();
        for addr in opt.listen_addresses.iter() {
            // add the WebRTC address
            listen_addresses.insert(
                ipaddr_to_multiaddr(addr)
                    .with(Protocol::Udp(PORT_WEBRTC))
                    .with(Protocol::WebRTCDirect),
            );
            // add the QUIC address
            listen_addresses.insert(
                ipaddr_to_multiaddr(addr)
                    .with(Protocol::Udp(PORT_QUIC))
                    .with(Protocol::QuicV1),
            );
            // add the TCP address
            listen_addresses.insert(ipaddr_to_multiaddr(addr).with(Protocol::Tcp(PORT_TCP)));
        }

        let mut external_addresses = HashSet::new();
        for addr in opt.external_addresses.iter() {
            external_addresses.insert(ipaddr_to_multiaddr(addr));
        }

        // keep them as Strings because they can be PeerId's or Multiaddr's
        let to_dial = opt.connect;

        // initialize the swarm
        let swarm = {
            let local_peer_id = PeerId::from(keypair.public());
            debug!("Local peer id: {local_peer_id}");

            // Initialize the autonat client behaviour
            let autonat_client = if opt.autonat_client {
                let cfg = AutonatClientConfig::default();
                Some(AutonatClient::new(OsRng, cfg))
            } else {
                None
            }
            .into();

            // Initialize the autonat server behaviour
            let autonat_server = if opt.autonat_server {
                Some(AutonatServer::new(OsRng))
            } else {
                None
            }
            .into();

            // Create the ConnectionLimits behaviour
            let connection_limits = {
                let cfg = connection_limits::ConnectionLimits::default()
                    .with_max_pending_incoming(Some(100))
                    .with_max_pending_outgoing(Some(100))
                    .with_max_established_per_peer(Some(10))
                    .with_max_established(Some(1000));
                ConnectionLimits::new(cfg)
            };

            // Create the Dcutr behaviour
            let dcutr = if opt.dcutr {
                Some(Dcutr::new(local_peer_id))
            } else {
                None
            }
            .into();

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
                    gossipsub::MessageAuthenticity::Signed(keypair.clone()),
                    gossipsub_config,
                )
                .expect("Correct configuration")
            };

            // Create an Identify behaviour
            let identify = {
                let cfg = IdentifyConfig::new(
                    IPFS_IDENTIFY_PROTOCOL_NAME.to_string(), // bug: https://github.com/libp2p/rust-libp2p/issues/5940
                    keypair.public(),
                )
                .with_agent_version(UNIVERSAL_CONNECTIVITY_AGENT.to_string());
                Identify::new(cfg)
            };

            // Create a Kademlia behaviour
            let kademlia: Toggle<Kademlia<MemoryStore>> = if opt.kademlia {
                let mut cfg = KademliaConfig::new(IPFS_KADEMLIA_PROTOCOL_NAME);
                cfg.set_query_timeout(Duration::from_secs(60));
                cfg.set_periodic_bootstrap_interval(Some(Duration::from_secs(
                    KADEMLIA_BOOTSTRAP_INTERVAL,
                )));
                let store = MemoryStore::new(local_peer_id);
                Some(Kademlia::with_config(local_peer_id, store, cfg))
            } else {
                None
            }
            .into();

            // Create the MemoryConnectionLimits behaviour
            let memory_connection_limits = MemoryConnectionLimits::with_max_percentage(0.9);

            // Create the RelayServer behaviour
            let relay_server = if opt.relay_server {
                let cfg = RelayServerConfig {
                    max_reservations: usize::MAX,
                    max_reservations_per_peer: 100,
                    reservation_rate_limiters: Vec::default(),
                    circuit_src_rate_limiters: Vec::default(),
                    max_circuits: usize::MAX,
                    max_circuits_per_peer: 100,
                    ..Default::default()
                };
                Some(RelayServer::new(local_peer_id, cfg))
            } else {
                None
            }
            .into();

            // Create the RequestResponse behaviour
            let request_response = {
                let cfg = RequestResponseConfig::default();
                RequestResponse::new([(FILE_EXCHANGE_PROTOCOL_NAME, ProtocolSupport::Full)], cfg)
            };

            // Initialize the overall peer behaviour
            let mut behaviour = Behaviour {
                autonat_client,
                autonat_server,
                connection_limits,
                dcutr,
                gossipsub,
                identify,
                kademlia,
                memory_connection_limits,
                relay_client: None.into(),
                relay_server,
                request_response,
            };

            // Build the swarm
            let sb = SwarmBuilder::with_existing_identity(keypair.clone())
                .with_tokio()
                .with_tcp(
                    TcpConfig::new().nodelay(true),
                    (TlsConfig::new, NoiseConfig::new), // passes the keypair to the constructors
                    YamuxConfig::default,
                )?
                .with_quic()
                .with_other_transport(|id_keys| {
                    Ok(webrtc::tokio::Transport::new(
                        id_keys.clone(),
                        tls_cert.clone(),
                    ))
                })?
                .with_dns()?;

            // if we are to be a relay client, add the relay client behaviour
            if opt.relay_client {
                sb.with_relay_client((TlsConfig::new, NoiseConfig::new), YamuxConfig::default)?
                    .with_behaviour(|_key, relay_client| {
                        behaviour.relay_client = Some(relay_client).into();
                        behaviour
                    })?
                    .build()
            } else {
                sb.with_behaviour(|_key| behaviour)?.build()
            }
        };

        Ok(Self {
            listen_addresses,
            external_addresses,
            to_dial,
            to_ui,
            from_ui,
            shutdown,
            swarm,
            bootstrap_query_id: None,
            start_providing_query_id: None,
            get_providers_query_id: None,
            get_closest_peers_query_id: HashSet::new(),
        })
    }

    /// Send a message to the UI
    pub async fn msg(&mut self, msg: impl ToString) -> anyhow::Result<()> {
        self.to_ui.send(Message::Event(msg.to_string())).await?;
        Ok(())
    }

    /// Update our external address if needed
    pub async fn update_external_address(&mut self, address: &Multiaddr) -> anyhow::Result<bool> {
        if !is_private_ip(address) && self.external_addresses.insert(address.clone()) {
            self.msg(format!("Adding external address: {address}"))
                .await?;
            self.swarm.add_external_address(address.clone());
            return Ok(true);
        }
        Ok(false)
    }

    /// Run the Peer
    pub async fn run(&mut self) -> anyhow::Result<()> {
        // Listen on the given addresses
        let addrs: Vec<Multiaddr> = self.listen_addresses.iter().cloned().collect();
        for addr in addrs.iter() {
            if let Err(e) = self.swarm.listen_on(addr.clone()) {
                self.msg(format!("Failed to listen on {addr}: {e}")).await?;
            }
        }

        // Set the external address if passed in
        let addrs: Vec<Multiaddr> = self.external_addresses.drain().collect();
        for addr in addrs.iter() {
            self.update_external_address(addr).await?;
        }

        // Dial the given addresses...they can be PeerId's or Multiaddr's
        for addr in self.to_dial.clone().iter() {
            if let Ok(addr) = addr.parse::<Multiaddr>() {
                // attempt to dial the address
                if let Err(e) = self.swarm.dial(addr.clone()) {
                    self.msg(format!("Failed to dial {addr}: {e}")).await?;
                } else {
                    self.msg(format!("Dialed {addr}")).await?;
                }

                // add the address to the kademlia routing table if it is enabled
                if let Some((multiaddr, peerid)) = split_peer_id(addr) {
                    if let Some(ref mut kad) = self.swarm.behaviour_mut().kademlia.as_mut() {
                        kad.add_address(&peerid, multiaddr);
                    }
                }
            } else if let Ok(addr) = addr.parse::<PeerId>() {
                // attempt to dial the address
                if let Err(e) = self.swarm.dial(addr) {
                    self.msg(format!("Failed to dial {addr}: {e}")).await?;
                } else {
                    self.msg(format!("Dialed {addr}")).await?;
                }
            } else {
                self.msg(format!("Failed to parse {addr}")).await?;
            }
        }

        // initiate a bootstrap of kademlia if it is enabled
        if let Some(ref mut kad) = self.swarm.behaviour_mut().kademlia.as_mut() {
            // parse the bootstrap multiaddrs
            let bootstrappers: Vec<Multiaddr> = IPFS_BOOTSTRAP_NODES
                .iter()
                .filter_map(|s| s.parse().ok())
                .collect();
            for addr in bootstrappers.iter() {
                if let Some((multiaddr, peerid)) = split_peer_id(addr.clone()) {
                    kad.add_address(&peerid, multiaddr);
                }
            }

            // start the bootstrap process
            match kad.bootstrap() {
                Ok(query_id) => {
                    self.bootstrap_query_id = Some(query_id);
                    self.msg("Bootstrapping Kademlia").await?;
                }
                Err(e) => {
                    self.msg(format!("Failed to bootstrap Kademlia: {e}"))
                        .await?;
                    self.msg(format!(
                        "Don't worry, it will try again in {KADEMLIA_BOOTSTRAP_INTERVAL} seconds"
                    ))
                    .await?;
                }
            }
        }

        // Initialize the gossipsub topics, the hashes are the same as the topic names
        let chat_topic = GossipsubIdentTopic::new(GOSSIPSUB_CHAT_TOPIC);
        let file_topic = GossipsubIdentTopic::new(GOSSIPSUB_CHAT_FILE_TOPIC);
        let peer_discovery = GossipsubIdentTopic::new(GOSSIPSUB_PEER_DISCOVERY);

        // Subscribe to the gossipsub topics
        info!("Subscribing to topics");
        for topic in [
            chat_topic.clone(),
            file_topic.clone(),
            peer_discovery.clone(),
        ] {
            if let Err(e) = self.swarm.behaviour_mut().gossipsub.subscribe(&topic) {
                debug!("Failed to subscribe to topic {topic}: {e}");
            }
        }

        // Create our loop ticker
        let mut tick = tokio::time::interval(Duration::from_millis(18));

        // Run the main loop
        loop {
            // process messages from the UI
            if let Ok(message) = self.from_ui.try_recv() {
                match message {
                    Message::Chat { data, .. } => {
                        error!("chat received");
                        match self
                            .swarm
                            .behaviour_mut()
                            .gossipsub
                            .publish(chat_topic.hash(), data)
                        {
                            Err(e) => debug!("Failed to publish chat message: {e}"),
                            _ => self.msg("Sent chat message from you".to_string()).await?,
                        }
                    }
                    Message::AllPeers { .. } => {
                        error!("all peers received");
                        let peers = self
                            .swarm
                            .behaviour()
                            .gossipsub
                            .all_peers()
                            .filter(|(_, topics)| !topics.is_empty())
                            .map(|(peer_id, topics)| {
                                (*peer_id, topics.iter().map(|t| t.to_string()).collect())
                            })
                            .collect();
                        self.to_ui.send(Message::AllPeers { peers }).await?;
                    }
                    _ => {
                        debug!("Unhandled message: {:?}", message);
                    }
                }
            }

            tokio::select! {
                _ = self.shutdown.cancelled() => {
                    info!("Unsubscribing from topics");
                    // Subscribe to the gossipsub topics
                    for topic in &[chat_topic, file_topic, peer_discovery] {
                        if !self.swarm.behaviour_mut().gossipsub.unsubscribe(topic) {
                            debug!("Failed to unsubscribe from topic {topic}");
                        }
                    }

                    info!("Shutting down the peer");
                    break;
                }

                _ = tick.tick() => {}

                Some(event) = self.swarm.next() => match event {

                    // When the swarm in initiates a dial
                    SwarmEvent::Dialing { peer_id, .. } => {
                        let peer_id = peer_id.map_or("Unknown".to_string(), |peer_id| peer_id.to_string());
                        debug!("Dialing {peer_id}");
                    }

                    // When we have confirmed our external address
                    SwarmEvent::ExternalAddrConfirmed { address } => {
                        let p2p_address = address
                            .clone()
                            .with(Protocol::P2p(*self.swarm.local_peer_id()));
                        self.msg(format!("Confirmed external address: {p2p_address}")).await?;
                    }

                    // When we successfully listen on an address
                    SwarmEvent::NewListenAddr { address, .. } => {
                        let p2p_address = address
                            .clone()
                            .with(Protocol::P2p(*self.swarm.local_peer_id()));
                        self.msg(format!("Listening on {p2p_address}"))
                            .await?;
                    }

                    // When we successfully connect to a peer
                    SwarmEvent::ConnectionEstablished { peer_id, .. } => {
                        debug!("Connected to {peer_id}");
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
                        self.to_ui.send(Message::RemovePeer(peer_id.into())).await?;

                        if let Some(ref mut kad) = self.swarm.behaviour_mut().kademlia.as_mut() {
                            kad.remove_peer(&peer_id);
                            info!("Removed {peer_id} from the routing table (if it was in there).");
                        }
                    }

                    // When we receive an autonat client event
                    SwarmEvent::Behaviour(BehaviourEvent::AutonatClient(AutonatClientEvent { tested_addr, server, result, .. })) => {
                        let result = result.map(|_| "Ok".to_string()).unwrap_or_else(|e| e.to_string());
                        debug!("NAT test to {tested_addr} with {server}: {result}");
                    }
                    // When we receive an autonat server event
                    SwarmEvent::Behaviour(BehaviourEvent::AutonatServer(AutonatServerEvent { tested_addr, client, result, .. })) => {
                        let result = result.map(|_| "Ok".to_string()).unwrap_or_else(|e| e.to_string());
                        self.msg(format!("NAT tested {tested_addr} to {client}: {result}")).await?;
                    }

                    // When we receive a dcutr event
                    SwarmEvent::Behaviour(BehaviourEvent::Dcutr(DcutrEvent { remote_peer_id, result })) => {
                        let result = result.map(|_| "Ok".to_string()).unwrap_or_else(|e| e.to_string());
                        self.msg(format!("Dcutr connection to {remote_peer_id}: {result}")).await?;
                    }

                    // When we receive a gossipsub event
                    SwarmEvent::Behaviour(BehaviourEvent::Gossipsub(event)) => match event {
                        GossipsubEvent::Message { .. } => {
                            let msg = UniversalConnectivityMessage::try_from(event)?;
                            self.msg(format!("{msg}")).await?;
                            match msg {
                                UniversalConnectivityMessage::Chat { from, data, ..} => {
                                    self.to_ui.send(Message::Chat{from, data}).await?;
                                    if let Some(peer) = from {
                                        self.to_ui.send(Message::AddPeer(peer)).await?;
                                    }
                                }
                                UniversalConnectivityMessage::File { from, data, .. } => {
                                    let file_id = String::from_utf8(data)?;
                                    if let Some(peer) = from {
                                        self.swarm.behaviour_mut().request_response.send_request(
                                            &peer.into(),
                                            FileRequest {
                                                file_id: file_id.clone(),
                                            },
                                        );
                                        self.msg(format!("Sent file request to {peer} for {file_id}")).await?;
                                    }
                                }
                                UniversalConnectivityMessage::PeerDiscovery { discovered_peer, discovered_addrs, .. } => {
                                    let mut msg = discovered_peer
                                        .map_or("\tDialing: Unknown".to_string(), |discovered_peer| {
                                            format!("\tDialing: {} ({})", discovered_peer.id(), discovered_peer)
                                        });
                                    // attempt to dial the discovered peer
                                    for addr in &discovered_addrs {
                                        if let Err(e) = self.swarm.dial(addr.clone()) {
                                            write!(msg, "\n\t\tError {e}").unwrap();
                                        } else {
                                            write!(msg, "\n\t\t{addr}").unwrap();
                                        }
                                    }
                                    self.msg(msg).await?;
                                    if let Some(peer) = discovered_peer {
                                        self.to_ui.send(Message::AddPeer(peer)).await?;
                                    }
                                }
                                _ => {}
                            }
                        }
                        GossipsubEvent::Subscribed { peer_id, topic } => {
                            debug!("{peer_id} subscribed to {topic}");
                            if topic.as_str() == GOSSIPSUB_CHAT_TOPIC {
                                self.to_ui.send(Message::AddPeer(peer_id.into())).await?;
                            }
                        }
                        GossipsubEvent::Unsubscribed { peer_id, topic } => {
                            debug!("{peer_id} unsubscribed from {topic}");
                            if topic.as_str() == GOSSIPSUB_CHAT_TOPIC {
                                self.to_ui.send(Message::RemovePeer(peer_id.into())).await?;
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
                            //self.update_external_address(&info.observed_addr).await?;
                            if info.agent_version == UNIVERSAL_CONNECTIVITY_AGENT {
                                let peer_id: PeerId = info.public_key.into();
                                let agent = format!("{} version: {}", info.agent_version, info.protocol_version);
                                let protocols = info.protocols.iter().map(|p| format!("\n\t\t{p}") ).collect::<Vec<String>>().join("");
                                self.msg(format!("Identify {peer_id}:\n\tagent: {agent}\n\tprotocols: {protocols}")).await?;
                                for addr in info.listen_addrs.iter() {
                                    if !is_private_ip(addr) {
                                        if let Err(e) = self.swarm.dial(addr.clone()) {
                                            self.msg(format!("Failed to dial {addr}: {e}")).await?;
                                        }
                                    }
                                }
                            }
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
                                    if let Some(ref mut kad) = self.swarm.behaviour_mut().kademlia.as_mut() {
                                        kad.remove_peer(&peer_id);
                                        info!("Removed {peer_id} from the routing table (if it was in there).");
                                    }
                                    self.to_ui.send(Message::RemovePeer(peer_id.into())).await?;
                                }
                                _ => {
                                    debug!("{error}");
                                }
                            }
                        }
                    }

                    // When we receive a kademlia event
                    SwarmEvent::Behaviour(BehaviourEvent::Kademlia(event)) => match event {
                        KademliaEvent::OutboundQueryProgressed { id, result, step, .. } => match result {
                            QueryResult::Bootstrap(result) => {
                                if let Some(query_id) = self.bootstrap_query_id {
                                    if id == query_id {
                                        match result {
                                            Ok(bootstrap) => {
                                                if step.last {
                                                    self.bootstrap_query_id = None;
                                                    self.msg("Kademlia bootstrapped".to_string()).await?;

                                                    let mut msgs = Vec::new();
                                                    if let Some(ref mut kad) = self.swarm.behaviour_mut().kademlia.as_mut() {
                                                        let key = RecordKey::new(&UNIVERSAL_CONNECTIVITY_AGENT);
                                                        // start providing the universal connectivity agent string
                                                        if let Ok(qid) = kad.start_providing(key.clone()) {
                                                            msgs.push(format!("Kademlia providing: {}", hex::encode(key.clone())));
                                                            self.start_providing_query_id = Some(qid);
                                                        }
                                                    }
                                                    for msg in msgs.iter() {
                                                        self.msg(msg).await?;
                                                    }
                                                } else {
                                                    self.msg(format!("Kademlia bootstrapping peer {}, remaining: {}", bootstrap.peer, bootstrap.num_remaining)).await?;
                                                }
                                            }
                                            Err(e) => {
                                                self.msg(format!("Failed to bootstrap Kademlia: {e}")).await?;
                                                self.bootstrap_query_id = None;
                                            }
                                        }
                                    }
                                }
                            }
                            QueryResult::GetClosestPeers(result) => {
                                if self.get_closest_peers_query_id.contains(&id) {
                                    match result {
                                        Ok(GetClosestPeersOk { peers, .. }) => {
                                            //if step.last {
                                                self.get_closest_peers_query_id.remove(&id);
                                                self.msg(format!("Kademlia {} potential universal connectivity peers:", peers.len())).await?;
                                                for peer in peers.iter().cloned() {
                                                    self.msg(format!("\t{}:", peer.peer_id)).await?;
                                                    for addr in peer.addrs.iter().take(1) {
                                                        self.msg(format!("\t\t{addr}")).await?;
                                                    }
                                                }
                                            /*
                                            } else {
                                                self.msg(format!("Kademlia getting closest peers: {}", peers.len())).await?;
                                            }
                                            */
                                        }
                                        Err(e) => {
                                            self.get_closest_peers_query_id.remove(&id);
                                            self.msg(format!("Failed to get closest peers: {e}")).await?;
                                        }
                                    }
                                }
                            }
                            QueryResult::GetProviders(result) => {
                                if let Some(query_id) = self.get_providers_query_id {
                                    if id == query_id {
                                        match result {
                                            Ok(GetProvidersOk::FoundProviders { providers, .. }) => {
                                                //if step.last {
                                                    self.get_providers_query_id = None;
                                                    let mut msgs = Vec::new();
                                                    if let Some(ref mut kad) = self.swarm.behaviour_mut().kademlia.as_mut() {
                                                        let peers: Vec<PeerId> = providers.iter().cloned().collect();
                                                        msgs.push(format!("Kademlia {} found providers", peers.len()));
                                                        for peer in peers.iter().cloned() {
                                                            self.get_closest_peers_query_id.insert(kad.get_closest_peers(peer));
                                                        }
                                                    }
                                                    for msg in msgs.iter() {
                                                        self.msg(msg).await?;
                                                    }
                                                /*
                                                } else {
                                                    self.get_providers_query_id = None;
                                                    self.msg(format!("Kademlia found getting providers: {}", providers.len())).await?;
                                                }
                                                */
                                            }
                                            Ok(GetProvidersOk::FinishedWithNoAdditionalRecord { closest_peers }) => {
                                                //if step.last {
                                                    self.get_providers_query_id = None;
                                                    let mut msgs = Vec::new();
                                                    if let Some(ref mut kad) = self.swarm.behaviour_mut().kademlia.as_mut() {
                                                        msgs.push(format!("Kademlia {} found providers", closest_peers.len()));
                                                        for peer in closest_peers.iter().cloned() {
                                                            self.get_closest_peers_query_id.insert(kad.get_closest_peers(peer));
                                                        }
                                                    }
                                                    for msg in msgs.iter() {
                                                        self.msg(msg).await?;
                                                    }
                                                /*
                                                } else {
                                                    self.get_providers_query_id = None;
                                                    self.msg(format!("Kademlia finished getting providers: {}", closest_peers.len())).await?;
                                                }
                                                */
                                            }
                                            Err(e) => {
                                                self.get_providers_query_id = None;
                                                self.msg(format!("Failed to get providers of universal connectivity agent string: {e}")).await?;

                                            }
                                        }
                                    }
                                }
                            }
                            QueryResult::GetRecord(result) => match result {
                                Ok(_record) => {
                                    self.msg("Kademlia record retrieved".to_string()).await?;
                                }
                                Err(e) => {
                                    self.msg(format!("Failed to retrieve Kademlia record: {e}")).await?;
                                }
                            }
                            QueryResult::StartProviding(result) => {
                                if let Some(query_id) = self.start_providing_query_id {
                                    if id == query_id {
                                        match result {
                                            Ok(AddProviderOk { key }) => {
                                                if step.last {
                                                    self.start_providing_query_id = None;
                                                    self.msg("Kademlia provider registered".to_string()).await?;
                                                    if let Some(ref mut kad) = self.swarm.behaviour_mut().kademlia.as_mut() {
                                                        // query for the providers of the universal connectivity agent string
                                                        self.get_providers_query_id = Some(kad.get_providers(key.clone()));
                                                    }
                                                    self.msg(format!("Kademlia getting providers for: {}", hex::encode(key.clone()))).await?;
                                                } else {
                                                    self.msg(format!("Kademlia adding provider record: {}", step.count)).await?;
                                                }
                                            }
                                            Err(e) => {
                                                self.start_providing_query_id = None;
                                                self.msg(format!("Failed to start providing Kademlia record: {e}")).await?;
                                            }
                                        }
                                    }
                                }
                            }
                            _ => {}
                        }
                        ref _other => {}
                    }

                    // When we receive a relay client event
                    SwarmEvent::Behaviour(BehaviourEvent::RelayClient(event)) => match event {
                        RelayClientEvent::ReservationReqAccepted { relay_peer_id, renewal, limit } => {
                            self.msg(format!("Relay reservation request accepted:\n\tfrom: {relay_peer_id}\n\trenewed: {renewal}\n\tlimit: {limit:?}")).await?;
                        }
                        RelayClientEvent::OutboundCircuitEstablished { relay_peer_id, .. } => {
                            self.msg(format!("Outbound relay circuit established:\n\tto: {relay_peer_id}")).await?;
                        }
                        RelayClientEvent::InboundCircuitEstablished { src_peer_id, .. } => {
                            self.msg(format!("Inbound relay circuit established:\n\tfrom: {src_peer_id}")).await?;
                        }
                    }

                    // When we receive a relay server event
                    SwarmEvent::Behaviour(BehaviourEvent::RelayServer(event)) => match event {
                        RelayServerEvent::ReservationReqAccepted { src_peer_id, renewed } => {
                            self.msg(format!("Relay reservation request accepted:\n\tfrom: {src_peer_id}\n\trenewed: {renewed}")).await?;
                        }
                        RelayServerEvent::ReservationReqDenied { src_peer_id, .. } => {
                            self.msg(format!("Relay reservation request denied: {src_peer_id}")).await?;
                        }
                        RelayServerEvent::ReservationTimedOut { src_peer_id } => {
                            self.msg(format!("Relay reservation timed out: {src_peer_id}")).await?;
                        }
                        RelayServerEvent::CircuitReqDenied { src_peer_id, dst_peer_id, .. } => {
                            self.msg(format!("Relay circuit request denied:\n\tfrom: {src_peer_id}\n\tto: {dst_peer_id}")).await?;
                        }
                        RelayServerEvent::CircuitReqAccepted { src_peer_id, dst_peer_id } => {
                            self.msg(format!("Relay circuit request accepted:\n\tfrom: {src_peer_id}\n\tto: {dst_peer_id}")).await?;
                        }
                        RelayServerEvent::CircuitClosed { src_peer_id, dst_peer_id, error } => {
                            self.msg(format!("Relay circuit closed:\n\tfrom: {src_peer_id}\n\tto: {dst_peer_id}\n\terror: {}", error.map_or("None".to_string(), |e| e.to_string()))).await?;
                        }
                        _ => {}
                    }

                    // When we receive a request_response event
                    SwarmEvent::Behaviour(BehaviourEvent::RequestResponse(event)) => match event {
                        RequestResponseEvent::Message { message, .. } => match message {
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
                        }
                        RequestResponseEvent::OutboundFailure {
                            request_id, error, ..
                        } => {
                            error!(
                                "request_response::Event::OutboundFailure for request {:?}: {:?}",
                                request_id, error
                            )
                        }
                        _ => {}
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

enum UniversalConnectivityMessage {
    Chat {
        propagation_source: PeerId,
        from: Option<ChatPeer>,
        data: Vec<u8>,
        seq_no: Option<u64>,
        topic: TopicHash,
    },
    File {
        propagation_source: PeerId,
        from: Option<ChatPeer>,
        data: Vec<u8>,
        seq_no: Option<u64>,
        topic: TopicHash,
    },
    PeerDiscovery {
        propagation_source: PeerId,
        from: Option<ChatPeer>,
        discovered_peer: Option<ChatPeer>,
        discovered_addrs: Vec<Multiaddr>,
        seq_no: Option<u64>,
        topic: TopicHash,
    },
    Unknown {
        propagation_source: PeerId,
        from: Option<ChatPeer>,
        data: Vec<u8>,
        seq_no: Option<u64>,
        topic: TopicHash,
    },
}

impl TryFrom<GossipsubEvent> for UniversalConnectivityMessage {
    type Error = anyhow::Error;

    fn try_from(event: GossipsubEvent) -> anyhow::Result<Self, Self::Error> {
        if let GossipsubEvent::Message {
            propagation_source,
            message,
            ..
        } = event
        {
            let from = message.source.map(Into::into);
            let data = message.data.clone();
            let seq_no = message.sequence_number;
            let topic = message.topic.clone();

            match topic.as_str() {
                GOSSIPSUB_CHAT_TOPIC => Ok(Self::Chat {
                    propagation_source,
                    from,
                    data,
                    seq_no,
                    topic,
                }),
                GOSSIPSUB_CHAT_FILE_TOPIC => Ok(Self::File {
                    propagation_source,
                    from,
                    data,
                    seq_no,
                    topic,
                }),
                GOSSIPSUB_PEER_DISCOVERY => {
                    let mut reader = BytesReader::from_bytes(&data);
                    let peer =
                        DiscoveredPeer::from_reader(&mut reader, &data).map_err(|_| fmt::Error)?;

                    let discovered_peer = {
                        if let Ok(pubkey) = PublicKey::try_decode_protobuf(&peer.publicKey) {
                            Some(PeerId::from(pubkey).into())
                        } else {
                            None
                        }
                    };

                    // only accept valid Multiaddrs
                    let discovered_addrs = {
                        let mut m: Vec<Multiaddr> = Vec::new();
                        for multiaddr in &peer.multiAddrs {
                            if let Ok(ma) = Multiaddr::try_from(multiaddr.to_vec()) {
                                m.push(ma);
                            }
                        }
                        m
                    };

                    Ok(Self::PeerDiscovery {
                        propagation_source,
                        from,
                        discovered_peer,
                        discovered_addrs,
                        seq_no,
                        topic,
                    })
                }
                _ => Ok(Self::Unknown {
                    propagation_source,
                    from,
                    data,
                    seq_no,
                    topic,
                }),
            }
        } else {
            Err(anyhow::anyhow!("Invalid GossipsubEvent"))
        }
    }
}

impl fmt::Display for UniversalConnectivityMessage {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Chat {
                propagation_source,
                from,
                data,
                seq_no,
                topic,
            } => {
                let propagation_source = {
                    let ps: ChatPeer = propagation_source.into();
                    format!("{} ({})", ps.id(), ps)
                };
                let chat_peer = from.as_ref().map_or("Unknown".to_string(), |from| {
                    format!("{} ({})", from.id(), from)
                });
                let source = from.as_ref().map_or("Unknown".to_string(), |peer| {
                    format!("{} ({})", peer.id(), peer)
                });
                let seq_no = seq_no.map_or("Unknown".to_string(), |seq_no| seq_no.to_string());
                let message =
                    String::from_utf8(data.to_vec()).unwrap_or("invalid UTF-8".to_string());
                write!(f, "Received chat message:\n\tp source: {propagation_source}\n\tsource: {source}\n\tseq no: {seq_no}\n\ttopic: {topic}\n\tfrom: {chat_peer}\n\tmsg: {message}")
            }
            Self::File {
                propagation_source,
                from,
                data,
                seq_no,
                topic,
            } => {
                let propagation_source = {
                    let ps: ChatPeer = propagation_source.into();
                    format!("{} ({})", ps.id(), ps)
                };
                let chat_peer = from.as_ref().map_or("Unknown".to_string(), |from| {
                    format!("{} ({})", from.id(), from)
                });
                let source = from.as_ref().map_or("Unknown".to_string(), |peer| {
                    format!("{} ({})", peer.id(), peer)
                });
                let seq_no = seq_no.map_or("Unknown".to_string(), |seq_no| seq_no.to_string());
                let message =
                    String::from_utf8(data.to_vec()).unwrap_or("invalid UTF-8".to_string());
                write!(f, "Received file offer:\n\tp source: {propagation_source}\n\tsource: {source}\n\tseq no: {seq_no}\n\ttopic: {topic}\n\tfrom: {chat_peer}\n\tfile id: {message}")
            }
            Self::PeerDiscovery {
                propagation_source,
                from,
                discovered_peer,
                discovered_addrs,
                seq_no,
                topic,
            } => {
                let propagation_source = {
                    let ps: ChatPeer = propagation_source.into();
                    format!("{} ({})", ps.id(), ps)
                };
                let chat_peer = from.as_ref().map_or("Unknown".to_string(), |from| {
                    format!("{} ({})", from.id(), from)
                });
                let source = from.as_ref().map_or("Unknown".to_string(), |peer| {
                    format!("{} ({})", peer.id(), peer)
                });
                let seq_no = seq_no.map_or("Unknown".to_string(), |seq_no| seq_no.to_string());
                let discovered_peer = discovered_peer
                    .map_or("Unknown".to_string(), |discovered_peer| {
                        format!("{} ({})", discovered_peer.id(), discovered_peer)
                    });
                write!(f, "Received peer discovery:\n\tp source: {propagation_source}\n\tsource: {source}\n\tseq no: {seq_no}\n\ttopic: {topic}\n\tfrom: {chat_peer}\n\tpeer: {discovered_peer}\n\tmultiaddrs: {}", discovered_addrs.len())
            }
            Self::Unknown {
                propagation_source,
                from,
                data,
                seq_no,
                topic,
            } => {
                let propagation_source = {
                    let ps: ChatPeer = propagation_source.into();
                    format!("{} ({})", ps.id(), ps)
                };
                let chat_peer = from.as_ref().map_or("Unknown".to_string(), |from| {
                    format!("{} ({})", from.id(), from)
                });
                let source = from.as_ref().map_or("Unknown".to_string(), |peer| {
                    format!("{} ({})", peer.id(), peer)
                });
                let seq_no = seq_no.map_or("Unknown".to_string(), |seq_no| seq_no.to_string());
                let fields = decode_unknown_protobuf(data).map_err(|_| fmt::Error)?;
                let data = pretty_print_fields(&fields);
                write!(f, "Received unknown message:\n\tp source: {propagation_source}\n\tsource: {source}\n\tseq no: {seq_no}\n\ttopic: {topic}\n\tfrom: {chat_peer}\n\tdata: {data}")
            }
        }
    }
}
