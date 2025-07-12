"""
Headless Service for Universal Connectivity Python Peer

This module provides a headless service that manages libp2p host, pubsub, and chat functionality
without any UI. It communicates with the UI through queues and events.
"""

import logging
import socket
import time
import multiaddr
import janus
import trio
import trio_asyncio
from queue import Empty
from typing import Optional, List, Dict, Any

from libp2p import new_host
from libp2p.crypto.rsa import create_new_key_pair
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub
from libp2p.tools.async_service.trio_service import background_trio_service
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.custom_types import TProtocol

from chatroom import ChatRoom, ChatMessage

logger = logging.getLogger("headless")

# Constants
DISCOVERY_SERVICE_TAG = "universal-connectivity"
GOSSIPSUB_PROTOCOL_ID = TProtocol("/meshsub/1.0.0")
DEFAULT_PORT = 9095


def find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))  # Bind to a free port provided by the OS
        return s.getsockname()[1]


class HeadlessService:
    """
    Headless service that manages libp2p components and provides data to UI through queues.
    """
    
    def __init__(self, nickname: str, port: int = 0, connect_addrs: List[str] = None):
        self.nickname = nickname
        self.port = port if port != 0 else find_free_port()
        self.connect_addrs = connect_addrs or []
        
        # libp2p components
        self.host = None
        self.pubsub = None
        self.gossipsub = None
        self.chat_room = None
        
        # Service state
        self.running = False
        self.ready = False
        self.full_multiaddr = None
        
        # Communication with UI
        self.message_queue = None  # UI receives messages from headless
        self.system_queue = None   # UI receives system messages from headless
        self.outgoing_queue = None # UI sends messages to headless
        
        # Events for synchronization
        self.ready_event = trio.Event()
        self.stop_event = trio.Event()
        
        logger.info(f"HeadlessService initialized - nickname: {nickname}, port: {self.port}")
    
    async def start(self):
        """Start the headless service."""
        logger.info("Starting headless service...")
        
        try:
            # Create queues for communication with UI
            self.message_queue = janus.Queue()      # Messages from headless to UI
            self.system_queue = janus.Queue()       # System messages from headless to UI  
            self.outgoing_queue = janus.Queue()     # Messages from UI to headless
            
            # Enable trio-asyncio mode
            async with trio_asyncio.open_loop():
                await self._run_service()
                    
        except Exception as e:
            logger.error(f"Failed to start headless service: {e}")
            raise
    
    async def _run_service(self):
        """Run the main service loop."""
        # Create key pair
        key_pair = create_new_key_pair()
        
        # Create listen address
        listen_addr = multiaddr.Multiaddr(f"/ip4/0.0.0.0/tcp/{self.port}")
        
        # Create libp2p host
        self.host = new_host(key_pair=key_pair)
        
        self.full_multiaddr = f"{listen_addr}/p2p/{self.host.get_id()}"
        logger.info(f"Host created with PeerID: {self.host.get_id()}")
        logger.info(f"Listening on: {listen_addr}")
        logger.info(f"Full multiaddr: {self.full_multiaddr}")
        
        # Create GossipSub with optimized parameters
        self.gossipsub = GossipSub(
            protocols=[GOSSIPSUB_PROTOCOL_ID],
            degree=3,
            degree_low=2,
            degree_high=4,
        )
        
        # Create PubSub
        self.pubsub = Pubsub(self.host, self.gossipsub)
        
        # Start host and pubsub services
        async with self.host.run(listen_addrs=[listen_addr]):
            logger.info("Initializing PubSub and GossipSub...")
            
            async with background_trio_service(self.pubsub):
                async with background_trio_service(self.gossipsub):
                    logger.info("Pubsub and GossipSub services started.")
                    await self.pubsub.wait_until_ready()
                    logger.info("Pubsub ready.")
                    
                    # Setup connections and chat room
                    await self._setup_connections()
                    await self._setup_chat_room()
                    
                    # Mark service as ready
                    self.ready = True
                    self.ready_event.set()
                    logger.info("✅ Headless service is ready")
                    
                    # Start message processing and wait for stop
                    async with trio.open_nursery() as nursery:
                        nursery.start_soon(self._process_messages)
                        nursery.start_soon(self._process_outgoing_messages)
                        nursery.start_soon(self._wait_for_stop)
    
    async def _setup_connections(self):
        """Setup connections to specified peers."""
        if not self.connect_addrs:
            return
        
        for addr_str in self.connect_addrs:
            try:
                logger.info(f"Attempting to connect to: {addr_str}")
                maddr = multiaddr.Multiaddr(addr_str)
                info = info_from_p2p_addr(maddr)
                logger.info(f"Connecting to peer: {info.peer_id}")
                await self.host.connect(info)
                logger.info(f"✅ Successfully connected to peer: {info.peer_id}")
                
                # Wait for connection to stabilize
                await trio.sleep(2)
                
                # Check pubsub peers
                connected_peers = list(self.pubsub.peers.keys())
                logger.info(f"PubSub peers after connection: {[str(p)[:8] for p in connected_peers]}")
                
                # Send system message to queue
                await self._send_system_message(f"Connected to peer: {str(info.peer_id)[:8]}")
                
            except Exception as e:
                logger.error(f"❌ Failed to connect to {addr_str}: {e}")
                await self._send_system_message(f"Failed to connect to {addr_str}: {e}")
    
    async def _setup_chat_room(self):
        """Setup the chat room."""
        logger.info("Setting up chat room...")
        
        self.chat_room = await ChatRoom.join_chat_room(
            host=self.host,
            pubsub=self.pubsub,
            nickname=self.nickname,
            multiaddr=self.full_multiaddr
        )
        
        # Add custom message handler to forward messages to UI
        self.chat_room.add_message_handler(self._handle_chat_message)
        
        # Start message handlers
        self.running = True
        
        logger.info(f"Chat room setup complete for '{self.nickname}'")
        await self._send_system_message(f"Joined chat room as '{self.nickname}'")
    
    async def _handle_chat_message(self, message: ChatMessage):
        """Handle incoming chat messages and forward to UI."""
        try:
            logger.info(f"📨 Received chat message: {message.message} from {message.sender_nick}")
            
            # Put message in queue for UI
            await self.message_queue.async_q.put({
                'type': 'chat_message',
                'message': message.message,
                'sender_nick': message.sender_nick,
                'sender_id': message.sender_id,
                'timestamp': message.timestamp
            })
            
            logger.debug(f"📤 Message forwarded to UI queue")
            
        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            logger.exception("Full traceback:")
    
    async def _send_system_message(self, message: str):
        """Send system message to UI queue."""
        try:
            if self.system_queue:
                await self.system_queue.async_q.put({
                    'type': 'system_message',
                    'message': message,
                    'timestamp': trio.current_time()
                })
        except Exception as e:
            logger.error(f"Error sending system message: {e}")
    
    async def _process_messages(self):
        """Process messages from chat room."""
        logger.info("Starting message processing...")
        
        try:
            # Start chat room message handlers
            await self.chat_room.start_message_handlers()
        except Exception as e:
            logger.error(f"Error in message processing: {e}")
    
    async def _process_outgoing_messages(self):
        """Process outgoing messages from UI to chat room."""
        logger.info("Starting outgoing message processing...")
        
        while self.running:
            try:
                # Check for messages from UI (non-blocking)
                try:
                    outgoing_data = self.outgoing_queue.sync_q.get_nowait()
                    if outgoing_data and 'message' in outgoing_data:
                        message = outgoing_data['message']
                        logger.info(f"📤 Sending message from UI: {message}")
                        
                        # Send message through chat room
                        if self.chat_room and self.running:
                            await self.chat_room.publish_message(message)
                            logger.debug(f"✅ Message sent successfully: {message}")
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
        
        logger.info("Outgoing message processing stopped")

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
                logger.debug(f"Message queued for sending: {message}")
            except Exception as e:
                logger.error(f"Failed to queue message: {e}")
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
    
    def get_message_queue(self):
        """Get the message queue for UI."""
        return self.message_queue
    
    def get_system_queue(self):
        """Get the system queue for UI."""
        return self.system_queue
    
    def get_outgoing_queue(self):
        """Get the outgoing queue for UI to send messages."""
        return self.outgoing_queue
    
    async def stop(self):
        """Stop the headless service."""
        logger.info("Stopping headless service...")
        self.stop_event.set()
        
        if self.chat_room:
            await self.chat_room.stop()
        
        # Close queues
        if self.message_queue:
            self.message_queue.close()
        if self.system_queue:
            self.system_queue.close()
        if self.outgoing_queue:
            self.outgoing_queue.close()
        
        logger.info("Headless service stopped")
