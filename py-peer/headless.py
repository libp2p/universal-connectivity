"""
Headless Service for Universal Connectivity Python Peer

This module provides a headless service that manages libp2p host, pubsub, and chat functionality
without any UI. It communicates with the UI through queues and events.
"""

import json
import logging
import os
import socket
import time
import traceback
import multiaddr
import janus
import trio
import trio_asyncio
import hashlib
from queue import Empty
from typing import List, Dict, Any, Set
from libp2p.discovery.bootstrap import BootstrapDiscovery
from libp2p.kad_dht.kad_dht import (
    DHTMode,
    KadDHT,
)
from libp2p import new_host
from libp2p.crypto.ed25519 import create_new_key_pair
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub
from libp2p.tools.anyio_service import background_trio_service
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.identity.identify.identify import identify_handler_for, parse_identify_response, ID as IDENTIFY_PROTOCOL_ID
from libp2p.utils.varint import read_length_prefixed_protobuf
from libp2p.peer.id import ID
from libp2p.custom_types import TProtocol
from libp2p.pubsub.gossipsub import PROTOCOL_ID, PROTOCOL_ID_V11, PROTOCOL_ID_V12
from libp2p.protocol_muxer.exceptions import (
    MultiselectClientError,
)
from libp2p.host.exceptions import (
    StreamFailure,
)
from chatroom import ChatRoom, ChatMessage
from libp2p.bitswap import BitswapClient, MemoryBlockStore
from libp2p.bitswap.dag import MerkleDag
from libp2p.network.config import ConnectionConfig

# File message prefix for pubsub
FILE_MESSAGE_PREFIX = "[FILE]"
# Default download directory
DEFAULT_DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

DEFAULT_SEED = "py-peer"  # Default seed for deterministic peer ID generation

logger = logging.getLogger("headless")

# Constants
DISCOVERY_SERVICE_TAG = "universal-connectivity"
PROTOCOL_ID_LIST = [PROTOCOL_ID, PROTOCOL_ID_V11, PROTOCOL_ID_V12]
DEFAULT_PORT = 9095

# Bootstrap nodes for peer discovery
BOOTSTRAP_PEERS = [
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa", 
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zp7ykQCj2gRNdrFeqQ1vG13rMb4sPS",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt",
    "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb"
]

def filter_compatible_peer_info(peer_info) -> bool:
    """Filter peer info to check if it has compatible addresses (TCP + IPv4)."""
    if not hasattr(peer_info, "addrs") or not peer_info.addrs:
        return False

    for addr in peer_info.addrs:
        addr_str = str(addr)
        if "/tcp/" in addr_str and "/ip4/" in addr_str and "/quic" not in addr_str:
            return True
    return False


class HeadlessService:
    """
    Headless service that manages libp2p components and provides data to UI through queues.
    """

    def __init__(self, nickname: str, port: int = 0, connect_addrs: List[str] = None, ui_mode: bool = False, strict_signing: bool = True, seed: str = None, topic: str = None):
        self.nickname = nickname
        self.port = port if port != 0 else 4001
        self.connect_addrs = connect_addrs or []
        self.ui_mode = ui_mode  # Flag to control logging behavior
        self.strict_signing = strict_signing  # Flag to control message signing
        self.seed = seed if seed else DEFAULT_SEED  # Seed string for deterministic peer ID (default: 'py-peer')
        self.topic = topic  # Custom topic to use instead of default

        # libp2p components
        self.host = None
        self.pubsub = None
        self.gossipsub = None
        self.dht = None
        self.chat_room = None
        
        # Bitswap components for file sharing
        self.bitswap_client = None
        self.merkle_dag = None
        self.block_store = MemoryBlockStore()
        
        # Service state
        self.running = False
        self.ready = False
        self.full_multiaddr = None
        
        # Communication with UI
        self.message_queue = None  # UI receives messages from headless
        self.system_queue = None   # UI receives system messages from headless
        self.outgoing_queue = None # UI sends messages to headless
        self.topic_subscription_queue = None  # UI sends topic subscription requests
        self.peer_connection_queue = None  # UI sends peer connection requests
        self.file_share_queue = None  # UI sends file sharing requests
        self.file_download_queue = None  # UI sends file download requests
        
        # Per-topic message storage
        self.topic_messages = {}  # {topic: [{'message': msg, 'timestamp': ts, 'read': bool}]}
        self.topic_unread_counts = {}  # {topic: int}
        
        # File sharing state
        self.shared_files = {}  # {cid_hex: {'filename': str, 'filesize': int, 'filepath': str}}
        self.download_dir = DEFAULT_DOWNLOAD_DIR
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Peer information storage for identify protocol
        self.peer_info_cache = {}  # Store peer info retrieved through identify
        
        # Events for synchronization
        self.ready_event = trio.Event()
        self.stop_event = trio.Event()
        
        if not ui_mode:  # Only log initialization if not in UI mode
            logger.info(f"HeadlessService initialized - nickname: {nickname}, port: {self.port}, strict_signing: {strict_signing}, seed: {self.seed}")
    
    async def monitor_peers(self):
        while True:
            logger.info(f"Connected peers are: {len(self.host.get_connected_peers())}")
            logger.info(f"Peers in peer store are: {len(self.host.get_peerstore().peers_with_addrs())}")
            logger.info(f"Peers in routing table are: {len(self.dht.routing_table.get_peer_ids())}")
            logger.info(f"Peers in pubsub are: {len(self.pubsub.peers.keys())}")
            await trio.sleep(5)

    async def start(self):
        """Start the headless service."""
        logger.info("Starting headless service...")
        
        try:
            # Create queues for communication with UI
            logger.debug("Creating message queues...")
            self.message_queue = janus.Queue()      # Messages from headless to UI
            self.system_queue = janus.Queue()       # System messages from headless to UI  
            self.outgoing_queue = janus.Queue()     # Messages from UI to headless
            self.topic_subscription_queue = janus.Queue()  # Topic subscription requests from UI
            self.peer_connection_queue = janus.Queue()  # Peer connection requests from UI
            self.file_share_queue = janus.Queue()  # File sharing requests from UI
            self.file_download_queue = janus.Queue()  # File download requests from UI
            logger.debug("Message queues created successfully")
            
            # Enable trio-asyncio mode
            async with trio_asyncio.open_loop():
                # Send initial system message to test queue inside trio context
                await self._send_system_message("Headless service starting...")
                await self._run_service()
                    
        except Exception as e:
            logger.error(f"Failed to start headless service: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            raise
    
    async def _run_service(self):
        """Run the main service loop."""
        secret = hashlib.sha256(self.seed.encode()).digest()
        logger.info(f"Using deterministic Ed25519 key derived from seed='{self.seed}'")
        key_pair = create_new_key_pair(seed=secret)
        
        # Create listen address
        listen_addr = multiaddr.Multiaddr(f"/ip4/0.0.0.0/tcp/{self.port}")

        config = ConnectionConfig(
        min_connections=10,
        low_watermark=12,
        high_watermark=40,
        max_connections=50,
        auto_connect_interval=5.0,  # Check every 5 seconds
        )
        
        # Create libp2p host WITHOUT bootstrap nodes initially
        # We'll connect to bootstrap nodes after pubsub is running
        self.host = new_host(
            key_pair=key_pair,
            connection_config=config,
            # bootstrap = BOOTSTRAP_PEERS
        )

        # Register identify protocol handler
        logger.info("📋 Registering identify protocol handler (raw protobuf format for go-libp2p compatibility)")
        identify_handler = identify_handler_for(self.host, use_varint_format=True)
        self.host.set_stream_handler(IDENTIFY_PROTOCOL_ID, identify_handler)
        logger.info(f"✅ Identify protocol handler registered for {IDENTIFY_PROTOCOL_ID} (raw format)")

        # Create DHT with random walk enabled
        self.dht = KadDHT(self.host, DHTMode.SERVER, enable_random_walk=True)
        logger.info("✅ DHT created with random walk enabled")
        
        self.full_multiaddr = f"{listen_addr}/p2p/{self.host.get_id()}"
        logger.info(f"Host created with PeerID: {self.host.get_id()}")
        logger.info(f"Listening on: {listen_addr}")
        logger.info(f"Full multiaddr: {self.full_multiaddr}")
        
        # Log GossipSub protocol configuration
        logger.info(f"📋 Configuring GossipSub with protocols: {PROTOCOL_ID_LIST}")
        logger.info(f"  Protocol 1: {PROTOCOL_ID}")
        logger.info(f"  Protocol 2: {PROTOCOL_ID_V11}")
        
        # Create GossipSub with optimized parameters (matching working pubsub.py)
        self.gossipsub = GossipSub(
            protocols=PROTOCOL_ID_LIST,
            degree=3,
            degree_low=2,
            degree_high=4,
            gossip_window=2,  # Smaller window for faster gossip
            gossip_history=5,  # Keep more history
            heartbeat_initial_delay=2.0,  # Start heartbeats sooner
            heartbeat_interval=5,  # More frequent heartbeats for testing
        )
        logger.info("✅ GossipSub router created successfully")
        
        # Create PubSub
        logger.info(f"🔐 Creating PubSub with strict_signing={self.strict_signing}")
        self.pubsub = Pubsub(self.host, self.gossipsub, strict_signing=self.strict_signing)
        logger.info("✅ PubSub service created successfully")
        
        # Create Bitswap client for file sharing
        self.bitswap_client = BitswapClient(self.host, self.block_store)
        self.merkle_dag = MerkleDag(self.bitswap_client)
        logger.info("✅ Bitswap client and MerkleDag created for file sharing")
        
        # Start host and pubsub services
        async with self.host.run(listen_addrs=[listen_addr]):
            logger.info("📡 Initializing PubSub, GossipSub, and DHT services...")
            try:
                async with background_trio_service(self.pubsub):
                    async with background_trio_service(self.gossipsub):
                        async with background_trio_service(self.dht):
                            logger.info("✅ Pubsub, GossipSub, and DHT services started.")
                            await self.pubsub.wait_until_ready()
                            logger.info("✅ Pubsub ready and operational.")
                            logger.info("✅ DHT service started with random walk enabled.")
                            bootstrap = None
                            if BOOTSTRAP_PEERS:
                                bootstrap = BootstrapDiscovery(self.host.get_network(), BOOTSTRAP_PEERS)
                                await bootstrap.start()
                            # Setup chat room BEFORE connections so topics are subscribed
                            # This ensures GossipSub protocol negotiation succeeds when connecting
                            await self._setup_chat_room()
                            
                            # Start Bitswap client
                            await self.bitswap_client.start()
                            logger.info("✅ Bitswap client started for file sharing")
                            
                            # Now setup connections after we're subscribed to topics
                            await self._setup_connections()
                            
                            # Setup connection event handlers for DHT
                            
                            # Mark service as ready
                            self.ready = True
                            self.ready_event.set()
                            logger.info("✅ Headless service is ready")
                            
                            # Start message processing and wait for stop
                            async with trio.open_nursery() as nursery:
                                # Set nursery for bitswap client
                                self.bitswap_client.set_nursery(nursery)
                                
                                nursery.start_soon(self._process_messages)
                                nursery.start_soon(self._process_outgoing_messages)
                                nursery.start_soon(self._process_topic_subscriptions)
                                nursery.start_soon(self._process_peer_connections)
                                nursery.start_soon(self._process_file_shares)
                                nursery.start_soon(self._process_file_downloads)
                                nursery.start_soon(self._wait_for_stop)
                                nursery.start_soon(self.monitor_peers)
                                # nursery.start_soon(maintain_connections, self.host)

            except (MultiselectClientError, StreamFailure) as e:
                logger.error(f"The protocol negotiation failed: {e}")
                pass
    
    async def _setup_connections(self):
        """Setup connections to specified peers with detailed protocol logging."""
        if not self.connect_addrs:
            return
        
        for addr_str in self.connect_addrs:
            try:
                logger.info(f"🔗 Attempting to connect to: {addr_str}")
                maddr = multiaddr.Multiaddr(addr_str)
                info = info_from_p2p_addr(maddr)
                logger.info(f"🔗 Parsed peer info - ID: {info.peer_id}, Addrs: {info.addrs}")
                
                # Check if already connected
                existing_conns = self.host.get_network().connections.get(info.peer_id)
                if existing_conns:
                    logger.info(f"✅ Already connected to peer: {info.peer_id}, skipping connection attempt")
                    continue
                
                # Log connection attempt
                logger.info(f"🔗 Initiating connection to peer: {info.peer_id}")
                await self.host.connect(info)
                logger.info(f"✅ TCP connection established to peer: {info.peer_id}")
                
                # Wait longer for protocol negotiation
                await trio.sleep(3)
                
                # Detailed protocol inspection
                logger.info(f"🔍 Starting protocol inspection for peer: {info.peer_id}")
                await self._inspect_peer_protocols(info.peer_id)
                
                # Check connection status
                try:
                    # In py-libp2p, we can check if peer is connected via the swarm
                    swarm = self.host.get_network()
                    if hasattr(swarm, 'connections') and info.peer_id in swarm.connections:
                        connections = [swarm.connections[info.peer_id]]
                        logger.info(f"📊 Active connections to peer {info.peer_id}: {len(connections)}")
                    else:
                        logger.info(f"📊 No direct connection info available for peer {info.peer_id}")
                except Exception as conn_err:
                    logger.warning(f"⚠️  Could not check connection status: {conn_err}")
                
                # Wait for PubSub protocol negotiation
                logger.info(f"⏳ Waiting for PubSub protocol negotiation...")
                await trio.sleep(3)
                
                # Check final PubSub status
                await self._check_pubsub_status(info.peer_id)
                
                await self._send_system_message(f"Connected to peer: {str(info.peer_id)[:8]}")
                
            except Exception as e:
                logger.error(f"❌ Failed to connect to {addr_str}: {e}")
                await self._send_system_message(f"Failed to connect to {addr_str}: {e}")
    
    async def _inspect_peer_protocols(self, peer_id):
        """Inspect and log all protocols supported by a peer."""
        try:
            logger.info(f"🔍 Checking peerstore for peer: {peer_id}")
            
            # Get peer's protocols from peerstore (simplified approach)
            peerstore = self.host.get_peerstore()
            
            # Check if we can access protocols - different py-libp2p versions have different APIs
            try:
                if hasattr(peerstore, 'get_protocols'):
                    protocols = peerstore.get_protocols(peer_id)
                elif hasattr(peerstore, 'protocols'):
                    protocols = peerstore.protocols(peer_id)
                else:
                    # Fallback - just log that we connected successfully
                    logger.info(f"✅ Successfully connected to peer {peer_id}")
                    logger.info(f"🔍 Protocol inspection not available in this py-libp2p version")
                    return
                    
                if protocols:
                    logger.info(f"📋 Peer {peer_id} supports {len(protocols)} protocols:")
                    for i, protocol in enumerate(protocols, 1):
                        logger.info(f"  {i}: {protocol}")
                        if "meshsub" in str(protocol) or "gossipsub" in str(protocol):
                            logger.info(f"  🎯 Found PubSub protocol: {protocol}")
                else:
                    logger.info(f"📋 No protocols found for peer {peer_id} yet (may still be negotiating)")
                    
            except Exception as proto_err:
                logger.info(f"🔍 Protocol details not accessible: {proto_err}")
                logger.info(f"✅ Peer {peer_id} connected successfully")
                    
        except Exception as e:
            logger.warning(f"⚠️  Error inspecting peer protocols: {e}")
            logger.info(f"✅ Peer {peer_id} connected successfully")
    
    async def _check_pubsub_status(self, peer_id):
        """Check the PubSub connection status with a specific peer."""
        try:
            logger.info(f"🔍 Checking PubSub status for peer: {peer_id}")
            
            # Check if peer is in pubsub.peers
            pubsub_peers = list(self.pubsub.peers.keys())
            logger.info(f"📡 Total PubSub peers: {len(pubsub_peers)}")
            for i, p in enumerate(pubsub_peers, 1):
                logger.info(f"  PubSub peer {i}: {p}")
            
            if peer_id in self.pubsub.peers:
                logger.info(f"✅ Peer {peer_id} is in PubSub mesh")
                
                # Check GossipSub specific status
                if hasattr(self.pubsub, 'router') and hasattr(self.pubsub.router, 'mesh'):
                    mesh = self.pubsub.router.mesh
                    logger.info(f"🕸️  GossipSub mesh status:")
                    logger.info(f"    Mesh topics: {list(mesh.keys())}")
                    for topic, topic_peers in mesh.items():
                        logger.info(f"    Topic '{topic}': {len(topic_peers)} peers")
                        if peer_id in topic_peers:
                            logger.info(f"    ✅ Peer {peer_id} is in mesh for topic '{topic}'")
                        else:
                            logger.warning(f"    ❌ Peer {peer_id} is NOT in mesh for topic '{topic}'")
            else:
                logger.warning(f"❌ Peer {peer_id} is NOT in PubSub mesh")
                logger.info("🔧 Possible reasons:")
                logger.info("  1. PubSub protocol negotiation failed")
                logger.info("  2. Peer doesn't support compatible GossipSub version")
                logger.info("  3. Network issues preventing PubSub handshake")
                
        except Exception as e:
            logger.error(f"❌ Error checking PubSub status: {e}")
    
    async def _setup_chat_room(self):
        """Setup the chat room."""
        logger.info("Setting up chat room...")
        
        self.chat_room = await ChatRoom.join_chat_room(
            host=self.host,
            pubsub=self.pubsub,
            nickname=self.nickname,
            multiaddr=self.full_multiaddr,
            headless_service=self,
            topic=self.topic
        )
        
        # Add custom message handler to forward messages to UI
        self.chat_room.add_message_handler(self._handle_chat_message)
        
        # Start message handlers
        self.running = True
        
        logger.info(f"Chat room setup complete for '{self.nickname}'")
        await self._send_system_message(f"Joined chat room as '{self.nickname}'")
    
    async def _handle_chat_message(self, message: ChatMessage):
        """Handle incoming chat messages and store them per-topic."""
        try:
            topic = message.topic or "default"
            
            # Initialize topic storage if needed
            if topic not in self.topic_messages:
                self.topic_messages[topic] = []
                self.topic_unread_counts[topic] = 0
            
            # Check if this is a file sharing message
            is_file_message = message.message.startswith(FILE_MESSAGE_PREFIX)
            
            if is_file_message:
                try:
                    file_meta_json = message.message[len(FILE_MESSAGE_PREFIX):]
                    file_meta = json.loads(file_meta_json)
                    
                    message_data = {
                        'type': 'file_message',
                        'message': message.message,
                        'sender_nick': message.sender_nick,
                        'sender_id': message.sender_id,
                        'timestamp': message.timestamp,
                        'topic': topic,
                        'read': False,
                        'file_cid': file_meta.get('cid', ''),
                        'file_name': file_meta.get('filename', 'unknown'),
                        'file_size': file_meta.get('filesize', 0),
                    }
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse file message: {e}")
                    # Fall back to regular message
                    message_data = {
                        'type': 'chat_message',
                        'message': message.message,
                        'sender_nick': message.sender_nick,
                        'sender_id': message.sender_id,
                        'timestamp': message.timestamp,
                        'topic': topic,
                        'read': False
                    }
            else:
                # Store message with unread flag
                message_data = {
                    'type': 'chat_message',
                    'message': message.message,
                    'sender_nick': message.sender_nick,
                    'sender_id': message.sender_id,
                    'timestamp': message.timestamp,
                    'topic': topic,
                    'read': False
                }
            
            self.topic_messages[topic].append(message_data)
            self.topic_unread_counts[topic] += 1
            
            # Log in simplified format only if not in UI mode
            if not self.ui_mode:
                if is_file_message:
                    logger.info(f"[{topic}] {message.sender_nick} shared a file: {message_data.get('file_name', 'unknown')}")
                else:
                    logger.info(f"[{topic}] {message.sender_nick}: {message.message}")
            
            # Still put message in queue for UI updates
            await self.message_queue.async_q.put(message_data)
            
        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            logger.exception("Full traceback:")
    
    async def _send_system_message(self, message: str):
        """Send system message to UI queue."""
        logger.debug(f"_send_system_message called with: {message}")
        try:
            if self.system_queue:
                logger.debug(f"System queue available, sending message: {message}")
                await self.system_queue.async_q.put({
                    'type': 'system_message',
                    'message': message,
                    'timestamp': trio.current_time()
                })
                logger.debug(f"System message sent successfully: {message}")
            else:
                logger.warning(f"System queue not available, cannot send message: {message}")
        except Exception as e:
            logger.error(f"Error sending system message: {e}")
            logger.exception("Full traceback:")
    
    async def _process_messages(self):
        """Process messages from chat room."""
        try:
            # Start chat room message handlers
            await self.chat_room.start_message_handlers()
        except Exception as e:
            logger.error(f"Error in message processing: {e}")
    
    async def _process_outgoing_messages(self):
        """Process outgoing messages from UI to chat room."""
        
        while self.running:
            try:
                # Check for messages from UI (non-blocking)
                try:
                    outgoing_data = self.outgoing_queue.sync_q.get_nowait()
                    if outgoing_data and 'message' in outgoing_data:
                        message = outgoing_data['message']
                        topic = outgoing_data.get('topic')  # Optional topic parameter
                        
                        # Send message through chat room
                        if self.chat_room and self.running:
                            if topic:
                                # Send to specific topic
                                success = await self.chat_room.publish_to_topic(topic, message)
                                if not self.ui_mode:
                                    logger.info(f"{self.nickname} (you) to {topic}: {message}")
                            else:
                                # Send to default chat topic
                                await self.chat_room.publish_message(message)
                                if not self.ui_mode:
                                    logger.info(f"{self.nickname} (you): {message}")
                        else:
                            logger.warning("Cannot send message: chat room not ready")
                            await self._send_system_message("Cannot send message: chat room not ready")
                            
                except Empty:
                    # No message available, that's fine
                    await trio.sleep(0.1)  # Brief pause to avoid busy loop
                except Exception as e:
                    logger.error(f"Error processing outgoing message: {e}")
                    await trio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in outgoing message processing: {e}")
                await trio.sleep(0.1)
    
    async def _process_topic_subscriptions(self):
        """Process topic subscription requests from UI."""
        
        while self.running:
            try:
                # Check for subscription requests from UI (non-blocking)
                try:
                    subscription_data = self.topic_subscription_queue.sync_q.get_nowait()
                    if subscription_data and 'topic' in subscription_data:
                        topic_name = subscription_data['topic']
                        
                        # Subscribe to the topic through chat room
                        if self.chat_room and self.running:
                            success = await self.chat_room.subscribe_to_topic(topic_name)
                            if success:
                                logger.info(f"Successfully subscribed to topic: {topic_name}")
                                await self._send_system_message(f"Subscribed to topic: {topic_name}")
                            else:
                                logger.warning(f"Failed to subscribe to topic: {topic_name}")
                                await self._send_system_message(f"Failed to subscribe to topic: {topic_name}")
                        else:
                            logger.warning("Cannot subscribe to topic: chat room not ready")
                            await self._send_system_message("Cannot subscribe to topic: chat room not ready")
                            
                except Empty:
                    # No request available, that's fine
                    await trio.sleep(0.1)  # Brief pause to avoid busy loop
                except Exception as e:
                    logger.error(f"Error processing topic subscription: {e}")
                    await trio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in topic subscription processing: {e}")
                await trio.sleep(0.1)
    
    async def _process_peer_connections(self):
        """Process peer connection requests from UI."""
        
        while self.running:
            try:
                # Check for connection requests from UI (non-blocking)
                try:
                    multiaddr_str = self.peer_connection_queue.sync_q.get_nowait()
                    if multiaddr_str:
                        logger.info(f"Processing peer connection request: {multiaddr_str}")
                        
                        # Parse and connect to the peer
                        try:
                            # Parse the multiaddress
                            maddr = multiaddr.Multiaddr(multiaddr_str)
                            
                            # Try to get peer info from the multiaddress
                            peer_info = info_from_p2p_addr(maddr)
                            
                            if peer_info:
                                # Connect to the peer
                                logger.info(f"Attempting to connect to peer: {peer_info.peer_id}")
                                await self.host.connect(peer_info)
                                logger.info(f"✅ Successfully connected to peer: {peer_info.peer_id}")
                                await self._send_system_message(f"Connected to peer: {peer_info.peer_id}")
                            else:
                                logger.error(f"Could not extract peer info from multiaddress: {multiaddr_str}")
                                await self._send_system_message(f"Invalid multiaddress format")
                                
                        except Exception as e:
                            logger.error(f"Failed to connect to peer {multiaddr_str}: {e}")
                            await self._send_system_message(f"Connection failed: {str(e)}")
                            
                except Empty:
                    # No request available, that's fine
                    await trio.sleep(0.1)  # Brief pause to avoid busy loop
                except Exception as e:
                    logger.error(f"Error processing peer connection: {e}")
                    await trio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in peer connection processing: {e}")
                await trio.sleep(0.1)

    async def _process_file_shares(self):
        """Process file sharing requests from UI."""
        while self.running:
            try:
                try:
                    share_data = self.file_share_queue.sync_q.get_nowait()
                    if share_data:
                        file_path = share_data.get('file_path')
                        topic = share_data.get('topic')
                        
                        if not file_path or not os.path.exists(file_path):
                            logger.error(f"File not found: {file_path}")
                            await self._send_system_message(f"File not found: {file_path}")
                            continue
                        
                        filename = os.path.basename(file_path)
                        filesize = os.path.getsize(file_path)
                        
                        logger.info(f"📁 Sharing file: {filename} ({filesize} bytes)")
                        await self._send_system_message(f"Preparing to share: {filename}...")
                        
                        try:
                            # Add file to Merkle DAG (chunks + stores in bitswap)
                            root_cid = await self.merkle_dag.add_file(
                                file_path,
                                wrap_with_directory=True
                            )
                            
                            cid_hex = root_cid.hex()
                            
                            # Track shared file locally
                            self.shared_files[cid_hex] = {
                                'filename': filename,
                                'filesize': filesize,
                                'filepath': file_path,
                            }
                            
                            logger.info(f"✅ File added to DAG. CID: {cid_hex}")
                            
                            # Create file sharing message with metadata
                            file_meta = {
                                'cid': cid_hex,
                                'filename': filename,
                                'filesize': filesize,
                            }
                            file_message = f"{FILE_MESSAGE_PREFIX}{json.dumps(file_meta)}"
                            
                            # Publish file message via pubsub to the topic
                            if topic and self.chat_room:
                                success = await self.chat_room.publish_to_topic(topic, file_message)
                                if success:
                                    logger.info(f"✅ File shared to topic '{topic}': {filename}")
                                    
                                    # Don't store in topic_messages here - the pubsub echo
                                    # will come back through _handle_chat_message and store it.
                                    # Only notify the UI immediately so it shows the bubble.
                                    await self.message_queue.async_q.put({
                                        'type': 'file_shared',
                                        'topic': topic,
                                        'file_cid': cid_hex,
                                        'file_name': filename,
                                        'file_size': filesize,
                                        'sender_nick': 'You',
                                        'sender_id': 'self',
                                        'timestamp': time.time(),
                                    })
                                else:
                                    await self._send_system_message(f"Failed to share file to topic")
                            else:
                                await self._send_system_message(f"No topic specified for file sharing")
                                
                        except Exception as e:
                            logger.error(f"Failed to share file: {e}")
                            logger.exception("Full traceback:")
                            await self._send_system_message(f"Failed to share file: {str(e)}")
                            
                except Empty:
                    await trio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error processing file share: {e}")
                    await trio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in file share processing: {e}")
                await trio.sleep(0.1)

    async def _process_file_downloads(self):
        """Process file download requests from UI."""
        while self.running:
            try:
                try:
                    download_data = self.file_download_queue.sync_q.get_nowait()
                    if download_data:
                        cid_hex = download_data.get('file_cid')
                        filename = download_data.get('file_name', 'unknown')
                        
                        if not cid_hex:
                            logger.error("No CID provided for download")
                            continue
                        
                        logger.info(f"📥 Downloading file: {filename} (CID: {cid_hex})")
                        await self._send_system_message(f"Downloading: {filename}...")
                        
                        try:
                            root_cid = bytes.fromhex(cid_hex)
                            
                            # Fetch file via bitswap
                            file_data, extracted_filename = await self.merkle_dag.fetch_file(
                                root_cid,
                                timeout=60.0
                            )
                            
                            # Use extracted filename if available, fallback to provided name
                            save_filename = extracted_filename or filename
                            
                            # Ensure download directory exists
                            os.makedirs(self.download_dir, exist_ok=True)
                            
                            # Handle filename conflicts
                            save_path = os.path.join(self.download_dir, save_filename)
                            if os.path.exists(save_path):
                                name, ext = os.path.splitext(save_filename)
                                counter = 1
                                while os.path.exists(save_path):
                                    save_path = os.path.join(self.download_dir, f"{name}_{counter}{ext}")
                                    counter += 1
                            
                            # Write file
                            with open(save_path, 'wb') as f:
                                f.write(file_data)
                            
                            logger.info(f"✅ File downloaded: {save_path} ({len(file_data)} bytes)")
                            
                            # Notify UI
                            await self.message_queue.async_q.put({
                                'type': 'file_downloaded',
                                'file_cid': cid_hex,
                                'file_name': save_filename,
                                'file_size': len(file_data),
                                'save_path': save_path,
                                'timestamp': time.time(),
                            })
                            
                        except Exception as e:
                            logger.error(f"Failed to download file: {e}")
                            logger.exception("Full traceback:")
                            await self.message_queue.async_q.put({
                                'type': 'file_download_failed',
                                'file_cid': cid_hex,
                                'file_name': filename,
                                'error': str(e),
                                'timestamp': time.time(),
                            })
                            
                except Empty:
                    await trio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error processing file download: {e}")
                    await trio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in file download processing: {e}")
                await trio.sleep(0.1)

    async def _wait_for_stop(self):
        """Wait for stop signal."""
        await self.stop_event.wait()
        logger.info("Stop signal received, shutting down...")
        self.running = False
    
    def send_message(self, message: str):
        """Send a message through the chat room (thread-safe)."""
        if self.outgoing_queue and self.running:
            try:
                # Put message in outgoing queue (sync call, safe from UI thread)
                self.outgoing_queue.sync_q.put({
                    'message': message,
                    'timestamp': time.time()
                })
            except Exception as e:
                logger.error(f"Failed to queue message: {e}")
        else:
            logger.warning("Cannot send message: outgoing queue not ready or service not running")
    
    def send_message_to_topic(self, topic: str, message: str):
        """Send a message to a specific topic (thread-safe)."""
        if self.outgoing_queue and self.running:
            try:
                # Put message with topic in outgoing queue
                self.outgoing_queue.sync_q.put({
                    'message': message,
                    'topic': topic,
                    'timestamp': time.time()
                })
            except Exception as e:
                logger.error(f"Failed to queue message to topic {topic}: {e}")
        else:
            logger.warning("Cannot send message: outgoing queue not ready or service not running")
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for UI."""
        if not self.ready:
            return {}
        
        return {
            'peer_id': str(self.host.get_id()),
            'nickname': self.nickname,
            'multiaddr': self.full_multiaddr,
            'connected_peers': self.chat_room.get_connected_peers() if self.chat_room else set(),
            'peer_count': self.chat_room.get_peer_count() if self.chat_room else 0
        }
    
    def get_subscribed_topics(self) -> Set[str]:
        """Get list of all subscribed topics."""
        if not self.chat_room:
            return set()
        return self.chat_room.get_subscribed_topics()
    
    def subscribe_to_topic(self, topic_name: str) -> bool:
        """
        Subscribe to a new topic (thread-safe wrapper).
        
        Args:
            topic_name: The name of the topic to subscribe to
            
        Returns:
            True if subscription request was queued, False otherwise
        """
        if not self.chat_room or not self.running:
            logger.warning("Cannot subscribe to topic: chat room not ready or service not running")
            return False
        
        try:
            # Put subscription request in queue (sync call, safe from UI thread)
            self.topic_subscription_queue.sync_q.put({
                'topic': topic_name,
                'timestamp': time.time()
            })
            logger.info(f"Queued subscription request for topic: {topic_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue topic subscription: {e}")
            return False
    
    def connect_to_peer(self, multiaddr: str) -> bool:
        """
        Connect to a peer using multiaddress (thread-safe wrapper).
        
        Args:
            multiaddr: The multiaddress of the peer to connect to
            
        Returns:
            True if connection request was queued, False otherwise
        """
        if not self.host or not self.running:
            logger.warning("Cannot connect to peer: host not ready or service not running")
            return False
        
        try:
            # Put connection request in queue (sync call, safe from UI thread)
            self.peer_connection_queue.sync_q.put(multiaddr)
            logger.info(f"Queued peer connection request: {multiaddr}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue peer connection: {e}")
            return False
    
    def share_file(self, file_path: str, topic: str) -> bool:
        """
        Share a file to a topic via bitswap (thread-safe wrapper).
        
        Args:
            file_path: Path to the file to share
            topic: The topic to share the file in
            
        Returns:
            True if file share request was queued, False otherwise
        """
        if not self.running or not self.file_share_queue:
            logger.warning("Cannot share file: service not ready")
            return False
        
        try:
            self.file_share_queue.sync_q.put({
                'file_path': file_path,
                'topic': topic,
                'timestamp': time.time(),
            })
            logger.info(f"Queued file share request: {file_path} -> {topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to queue file share: {e}")
            return False
    
    def download_file(self, file_cid: str, file_name: str = "unknown") -> bool:
        """
        Download a file by CID via bitswap (thread-safe wrapper).
        
        Args:
            file_cid: Hex CID of the file to download
            file_name: Expected filename
            
        Returns:
            True if download request was queued, False otherwise
        """
        if not self.running or not self.file_download_queue:
            logger.warning("Cannot download file: service not ready")
            return False
        
        try:
            self.file_download_queue.sync_q.put({
                'file_cid': file_cid,
                'file_name': file_name,
                'timestamp': time.time(),
            })
            logger.info(f"Queued file download request: {file_name} (CID: {file_cid[:16]}...)")
            return True
        except Exception as e:
            logger.error(f"Failed to queue file download: {e}")
            return False
    
    def get_message_queue(self):
        """Get the message queue for UI."""
        return self.message_queue
    
    def get_system_queue(self):
        """Get the system queue for UI."""
        return self.system_queue
    
    def get_topic_messages(self, topic: str) -> List[Dict[str, Any]]:
        """
        Get all messages for a specific topic.
        
        Args:
            topic: The topic name
            
        Returns:
            List of message dictionaries
        """
        return self.topic_messages.get(topic, [])
    
    def get_all_topics_with_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all subscribed topics with their message counts and unread status.
        
        Returns:
            Dict mapping topic names to info dicts containing:
            - unread_count: Number of unread messages
            - total_count: Total number of messages
            - last_message: Most recent message (if any)
        """
        result = {}
        subscribed_topics = self.get_subscribed_topics()
        
        for topic in subscribed_topics:
            messages = self.topic_messages.get(topic, [])
            unread_count = self.topic_unread_counts.get(topic, 0)
            
            info = {
                'unread_count': unread_count,
                'total_count': len(messages),
                'last_message': messages[-1] if messages else None
            }
            result[topic] = info
        
        return result
    
    def mark_topic_as_read(self, topic: str):
        """
        Mark all messages in a topic as read.
        
        Args:
            topic: The topic name
        """
        if topic in self.topic_messages:
            for message in self.topic_messages[topic]:
                message['read'] = True
            self.topic_unread_counts[topic] = 0
            logger.debug(f"Marked all messages in topic '{topic}' as read")
    
    def get_unread_count(self, topic: str) -> int:
        """
        Get the count of unread messages for a topic.
        
        Args:
            topic: The topic name
            
        Returns:
            Number of unread messages
        """
        return self.topic_unread_counts.get(topic, 0)
    
    def get_outgoing_queue(self):
        """Get the outgoing queue for UI to send messages."""
        return self.outgoing_queue
    
    async def get_peer_info_via_identify(self, peer_id):
        """Get peer information using official identify protocol implementation."""
        try:
            logger.info(f"🔍 Requesting identify info from peer: {peer_id}")
            logger.info(f"peers in peer store are: {self.host.get_peerstore().peers_with_addrs()}")
            logger.info(f"address of peer {peer_id} is {self.host.get_peerstore().peer_info(peer_id).addrs} ")
            
            # Create a stream to the peer for identify protocol - use tuple format as in example
            stream = await self.host.new_stream(peer_id, (IDENTIFY_PROTOCOL_ID,))
            
            try:
                # Use official py-libp2p utilities to read the response
                # Use raw protobuf format (use_varint_format=False) for go-libp2p compatibility
                # go-libp2p uses the old/raw format, not the newer varint length-prefixed format
                response_bytes = await read_length_prefixed_protobuf(stream, use_varint_format=True)
                
                if not response_bytes:
                    logger.warning(f"Empty identify response from peer: {peer_id}")
                    return None
                
                # Parse the identify response using official parser
                identify_info = parse_identify_response(response_bytes)
                
                logger.info(f"✅ Received identify info from {peer_id}")
                logger.info(f"  - Protocol Version: {identify_info.protocol_version}")
                logger.info(f"  - Agent Version: {identify_info.agent_version}")
                logger.info(f"  - Public Key: {len(identify_info.public_key)} bytes")
                logger.info(f"  - Listen Addresses: {len(identify_info.listen_addrs)} addresses")
                logger.info(f"  - Protocols: {len(identify_info.protocols)} protocols")
                
                # Store the peer info in our cache
                self.peer_info_cache[str(peer_id)] = {
                    'public_key': identify_info.public_key,
                    'protocol_version': identify_info.protocol_version,
                    'agent_version': identify_info.agent_version,
                    'listen_addrs': identify_info.listen_addrs,
                    'protocols': identify_info.protocols,
                    'timestamp': time.time()
                }
                
                return identify_info
                
            finally:
                await stream.close()
                
        except Exception as e:
            logger.error(f"❌ Failed to get identify info from peer {peer_id}: {e}")
            return None
    
    async def get_cached_peer_info(self, peer_id: str):
        """Get cached peer info, or fetch it if not available."""
        peer_id_str = str(peer_id)
        
        # Check if we have cached info
        if peer_id_str in self.peer_info_cache:
            cached_info = self.peer_info_cache[peer_id_str]
            # Check if cache is not too old (5 minutes)
            if time.time() - cached_info['timestamp'] < 300:
                return cached_info
            else:
                logger.debug(f"Cached info for {peer_id_str} is stale, refreshing")
        
        # Fetch fresh info
        try:
            peer_id_obj = ID.from_base58(peer_id_str) if isinstance(peer_id, str) else peer_id
            identify_info = await self.get_peer_info_via_identify(peer_id_obj)
            
            if identify_info:
                return self.peer_info_cache[peer_id_str]
        except Exception as e:
            logger.error(f"❌ Failed to get peer info for {peer_id_str}: {e}")
        
        return None
    
    def get_public_key_for_peer(self, peer_id: str):
        """Get public key for a peer (synchronous access to cache)."""
        peer_id_str = str(peer_id)
        if peer_id_str in self.peer_info_cache:
            return self.peer_info_cache[peer_id_str]['public_key']
        return None
    
    async def stop(self):
        """Stop the headless service."""
        logger.info("Stopping headless service...")
        self.stop_event.set()
        
        if self.chat_room:
            await self.chat_room.stop()
        
        # Stop bitswap client
        if self.bitswap_client:
            await self.bitswap_client.stop()
        
        # Close queues
        if self.message_queue:
            self.message_queue.close()
        if self.system_queue:
            self.system_queue.close()
        if self.outgoing_queue:
            self.outgoing_queue.close()
        if self.topic_subscription_queue:
            self.topic_subscription_queue.close()
        if self.peer_connection_queue:
            self.peer_connection_queue.close()
        if self.file_share_queue:
            self.file_share_queue.close()
        if self.file_download_queue:
            self.file_download_queue.close()
        
        logger.info("Headless service stopped")
