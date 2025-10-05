"""
ChatRoom module for Universal Connectivity Python Peer

This module handles chat room functionality including message handling,
pubsub subscriptions, and peer discovery.
"""

import base58
import logging
import time
import trio
from dataclasses import dataclass
from typing import Set, Optional, AsyncIterator

from libp2p.host.basic_host import BasicHost
from libp2p.pubsub.pb.rpc_pb2 import Message
from libp2p.pubsub.pubsub import Pubsub

logger = logging.getLogger("chatroom")

# Create a separate logger for system messages
system_logger = logging.getLogger("system_messages")
system_handler = logging.FileHandler("system_messages.txt", mode='a')
system_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
system_logger.addHandler(system_handler)
system_logger.setLevel(logging.INFO)
system_logger.propagate = False  # Don't send to parent loggers

# Chat room buffer size for incoming messages
CHAT_ROOM_BUF_SIZE = 128

# Topics used in the chat system
PUBSUB_DISCOVERY_TOPIC = "universal-connectivity-browser-peer-discovery"
CHAT_TOPIC = "universal-connectivity"


@dataclass
class ChatMessage:
    """Represents a chat message."""
    message: str
    sender_id: str
    sender_nick: str
    topic: str = None  # Topic the message was received on
    timestamp: Optional[float] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class ChatRoom:
    """
    Represents a subscription to PubSub topics for chat functionality.
    Messages can be published to topics and received messages are handled
    through callback functions.
    """
    
    def __init__(self, host: BasicHost, pubsub: Pubsub, nickname: str, multiaddr: str = None, headless_service=None, topic: str = None):
        self.host = host
        self.pubsub = pubsub
        self.nickname = nickname
        self.peer_id = str(host.get_id())
        self.multiaddr = multiaddr or f"unknown/{self.peer_id}"
        self.headless_service = headless_service  # Reference for identify protocol
        
        # Use custom topic if provided, otherwise use default
        self.chat_topic = topic if topic else CHAT_TOPIC
        
        # Subscriptions - now a dictionary to track all subscriptions
        self.subscriptions = {}  # topic_name -> subscription object
        self.chat_subscription = None
        self.discovery_subscription = None
        
        # Message handlers
        self.message_handlers = []
        self.system_message_handlers = []
        
        # Topic handlers - stores (topic_name, subscription) for dynamic topics
        self.topic_handlers = []
        self.active_topic_handlers = set()  # Track which topics already have handlers running
        
        # Running state
        self.running = False
        self.nursery = None  # Store nursery reference for spawning new handlers
        
        logger.info(f"ChatRoom initialized for peer {self.peer_id[:8]}... with nickname '{nickname}'")
        logger.info(f"Chat topic: {self.chat_topic}")
        self._log_system_message("Universal Connectivity Chat Started")
        self._log_system_message(f"Nickname: {nickname}")
        self._log_system_message(f"Topic: {self.chat_topic}")
        self._log_system_message(f"Multiaddr: {self.multiaddr}")
        self._log_system_message("Commands: /quit, /peers, /status, /multiaddr")
    
    def _log_system_message(self, message: str):
        """Log system message to file."""
        system_logger.info(message)
    
    @classmethod
    async def join_chat_room(cls, host: BasicHost, pubsub: Pubsub, nickname: str, multiaddr: str = None, headless_service=None, topic: str = None) -> "ChatRoom":
        """Create and join a chat room."""
        chat_room = cls(host, pubsub, nickname, multiaddr, headless_service, topic)
        await chat_room._subscribe_to_topics()
        chat_room._log_system_message(f"Joined chat room as '{nickname}'")
        return chat_room
    
    async def _subscribe_to_topics(self):
        """Subscribe to all necessary topics."""
        try:
            # Subscribe to chat topic (either custom or default)
            self.chat_subscription = await self.pubsub.subscribe(self.chat_topic)
            self.subscriptions[self.chat_topic] = self.chat_subscription
            logger.info(f"Subscribed to chat topic: {self.chat_topic}")
            
            # Add chat topic to handlers list
            self.topic_handlers.append((self.chat_topic, self.chat_subscription))
            
            # Subscribe to discovery topic
            self.discovery_subscription = await self.pubsub.subscribe(PUBSUB_DISCOVERY_TOPIC)
            self.subscriptions[PUBSUB_DISCOVERY_TOPIC] = self.discovery_subscription
            logger.info(f"Subscribed to discovery topic: {PUBSUB_DISCOVERY_TOPIC}")
            
            # Add discovery topic to handlers list
            self.topic_handlers.append((PUBSUB_DISCOVERY_TOPIC, self.discovery_subscription))
            
        except Exception as e:
            logger.error(f"Failed to subscribe to topics: {e}")
            self._log_system_message(f"ERROR: Failed to subscribe to topics: {e}")
            raise
    
    async def publish_message(self, message: str):
        """Publish a chat message in plain text format (Go-compatible)."""
        try:
            # Check if we have any peers connected
            peer_count = len(self.pubsub.peers)
            logger.info(f"📤 Publishing message to {peer_count} peers: {message}")
            logger.info(f"Total pubsub peers: {list(self.pubsub.peers.keys())}")
            
            # Send plain text message (Go-compatible format) to the custom topic
            print(f"Sending message {message}")
            await self.pubsub.publish(self.chat_topic, message.encode())
            logger.info(f"✅ Message published successfully to topic '{self.chat_topic}'")
            
            if peer_count == 0:
                print(f"⚠️  No peers connected - message sent to topic but no one will receive it")
            else:
                print(f"✓ Message sent to {peer_count} peer(s)")
                
        except Exception as e:
            logger.error(f"❌ Failed to publish message: {e}")
            print(f"❌ Error sending message: {e}")
            self._log_system_message(f"ERROR: Failed to publish message: {e}")
    
    async def publish_to_topic(self, topic: str, message: str):
        """Publish a message to a specific topic."""
        try:
            # Check if we're subscribed to this topic
            if topic not in self.subscriptions:
                logger.warning(f"Not subscribed to topic: {topic}")
                return False
            
            peer_count = len(self.pubsub.peers)
            logger.info(f"📤 Publishing message to topic '{topic}' with {peer_count} peers: {message}")
            
            # Send plain text message
            await self.pubsub.publish(topic, message.encode())
            logger.info(f"✅ Message published successfully to topic '{topic}'")
            
            return True
                
        except Exception as e:
            logger.error(f"❌ Failed to publish message to topic '{topic}': {e}")
            self._log_system_message(f"ERROR: Failed to publish message to topic '{topic}': {e}")
            return False
    
    async def _validate_message_with_identify(self, message, sender_id):
        """Validate message using identify protocol to get sender's public key.
        
        This should only be called for messages from OTHER peers that don't include
        a public key in the message data.
        """
        # Safety check: never try to identify ourselves
        if sender_id == self.peer_id:
            logger.debug(f"⏭️  Skipping identify for own peer ID {sender_id}")
            return True
            
        if not self.headless_service:
            logger.warning("No headless service available for identify protocol")
            return True  # Default to accepting message if no identify available
        
        try:
            # Get peer info via identify protocol (this will cache it)
            peer_info = await self.headless_service.get_cached_peer_info(sender_id)
            
            if peer_info and peer_info.get('public_key'):
                logger.info(f"✅ Retrieved public key for {sender_id} via identify protocol")
                # Here you could add actual message signature validation
                # For now, we just log that we got the public key
                return True
            else:
                logger.warning(f"⚠️  Could not get public key for {sender_id} via identify protocol")
                return True  # Still accept message but log the issue
                
        except Exception as e:
            logger.error(f"❌ Error validating message with identify: {e}")
            return True  # Default to accepting message on error
    
    async def _handle_topic_messages(self, topic_name: str, subscription):
        """Handle incoming messages for any subscribed topic (including chat and discovery)."""
        logger.debug(f"📨 Starting message handler for topic: {topic_name}")
        
        try:
            async for message in self._message_stream(subscription):
                try:
                    # Handle messages in the same way as chat messages
                    raw_data = message.data.decode()
                    sender_id = base58.b58encode(message.from_id).decode() if message.from_id else "unknown"
                    
                    # Check if this is our own message
                    is_own_message = sender_id == self.peer_id
                    
                    # Only validate messages from other peers
                    if not is_own_message:
                        if not message.key:
                            logger.debug(f"🔍 Message from {sender_id} has no public key, using identify protocol")
                            is_valid = await self._validate_message_with_identify(message, sender_id)
                            if not is_valid:
                                logger.warning(f"⚠️  Message validation failed for {sender_id}, skipping")
                                continue
                        else:
                            logger.debug(f"✅ Message from {sender_id} includes public key")
                    else:
                        logger.debug(f"📝 Processing own message from {sender_id} (no validation needed)")
                    
                    # Format sender nickname
                    if is_own_message:
                        sender_nick = f"{self.nickname}"
                    else:
                        sender_nick = sender_id[-8:] if len(sender_id) > 8 else sender_id
                    
                    actual_message = raw_data
                    
                    logger.info(f"📨 Received message on topic '{topic_name}' from {sender_id} ({sender_nick}): {actual_message}")
                    
                    # Create ChatMessage object for handlers
                    chat_msg = ChatMessage(
                        message=actual_message,
                        sender_id=sender_id,
                        sender_nick=sender_nick,
                        topic=topic_name
                    )
                    
                    # Call message handlers
                    for handler in self.message_handlers:
                        try:
                            await handler(chat_msg)
                        except Exception as e:
                            logger.error(f"❌ Error in message handler: {e}")
                    
                    # Default console output if no handlers
                    if not self.message_handlers:
                        print(f"[{topic_name}][{chat_msg.sender_nick}]: {chat_msg.message}")
                
                except Exception as e:
                    logger.error(f"❌ Error processing message on topic '{topic_name}': {e}")
        
        except Exception as e:
            logger.error(f"❌ Error in message handler for topic '{topic_name}': {e}")
    
    async def _message_stream(self, subscription) -> AsyncIterator[Message]:
        """Create an async iterator for subscription messages."""
        while self.running:
            try:
                message = await subscription.get()
                yield message
            except Exception as e:
                logger.error(f"Error getting message from subscription: {e}")
                await trio.sleep(1)  # Avoid tight loop on error
    
    async def start_message_handlers(self):
        """Start all message handler tasks."""
        self.running = True
        
        async with trio.open_nursery() as nursery:
            # Store nursery reference for dynamic task spawning
            self.nursery = nursery
            
            # Start background task to monitor for new topic subscriptions
            nursery.start_soon(self._monitor_new_topics)
    
    async def _monitor_new_topics(self):
        """Monitor for new topic subscriptions and start handlers for them."""
        while self.running:
            try:
                # Check if there are any new topics that need handlers
                for topic_name, subscription in self.topic_handlers:
                    if topic_name not in self.active_topic_handlers:
                        logger.info(f"Starting message handler for topic: {topic_name}")
                        
                        # Use generic handler for all topics (including chat and discovery)
                        self.nursery.start_soon(self._handle_topic_messages, topic_name, subscription)
                        self.active_topic_handlers.add(topic_name)
                
                # Check periodically (every 0.5 seconds)
                await trio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in topic monitor: {e}")
                await trio.sleep(1)
    
    def add_message_handler(self, handler):
        """Add a custom message handler."""
        self.message_handlers.append(handler)
    
    def add_system_message_handler(self, handler):
        """Add a custom system message handler."""
        self.system_message_handlers.append(handler)
    
    async def run_interactive(self):
        """Run interactive chat mode."""
        print(f"\n=== Universal Connectivity Chat ===")
        print(f"Nickname: {self.nickname}")
        print(f"Peer ID: {self.peer_id}")
        print(f"Type messages and press Enter to send. Type 'quit' to exit.")
        print(f"Commands: /peers, /status, /multiaddr")
        print()
        
        async with trio.open_nursery() as nursery:
            # Start message handlers
            nursery.start_soon(self.start_message_handlers)
            
            # Start input handler
            nursery.start_soon(self._input_handler)
    
    async def _input_handler(self):
        """Handle user input in interactive mode."""
        try:
            while self.running:
                try:
                    # Use trio's to_thread to avoid blocking the event loop
                    message = await trio.to_thread.run_sync(input)
                    
                    if message.lower() in ["quit", "exit", "q"]:
                        print("Goodbye!")
                        self.running = False
                        break
                    
                    # Handle special commands
                    elif message.strip() == "/peers":
                        peers = self.get_connected_peers()
                        if peers:
                            print(f"📡 Connected peers ({len(peers)}):")
                            for peer in peers:
                                print(f"  - {peer[:8]}...")
                        else:
                            print("📡 No peers connected")
                        continue
                    
                    elif message.strip() == "/multiaddr":
                        print(f"\n📋 Copy this multiaddress:")
                        print(f"{self.multiaddr}")
                        print()
                        continue
                    
                    elif message.strip() == "/status":
                        peer_count = self.get_peer_count()
                        subscribed_topics = ", ".join(sorted(self.get_subscribed_topics()))
                        print(f"📊 Status:")
                        print(f"  - Multiaddr: {self.multiaddr}")
                        print(f"  - Nickname: {self.nickname}")
                        print(f"  - Connected peers: {peer_count}")
                        print(f"  - Chat topic: {self.chat_topic}")
                        print(f"  - Subscribed topics: {subscribed_topics}")
                        continue
                    
                    if message.strip():
                        await self.publish_message(message)
                
                except EOFError:
                    print("\nGoodbye!")
                    self.running = False
                    break
                except Exception as e:
                    logger.error(f"Error in input handler: {e}")
                    await trio.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Fatal error in input handler: {e}")
            self.running = False
    
    async def stop(self):
        """Stop the chat room."""
        self.running = False
        logger.info("ChatRoom stopped")
    
    def get_connected_peers(self) -> Set[str]:
        """Get list of connected peer IDs."""
        return set(str(peer_id) for peer_id in self.pubsub.peers.keys())
    
    def get_peer_count(self) -> int:
        """Get number of connected peers."""
        return len(self.pubsub.peers)
    
    def get_subscribed_topics(self) -> Set[str]:
        """Get list of all subscribed topics."""
        return set(self.subscriptions.keys())
    
    async def subscribe_to_topic(self, topic_name: str) -> bool:
        """
        Subscribe to a new topic dynamically.
        
        Args:
            topic_name: The name of the topic to subscribe to
            
        Returns:
            True if subscription was successful, False otherwise
        """
        try:
            if topic_name in self.subscriptions:
                logger.warning(f"Already subscribed to topic: {topic_name}")
                return False
            
            logger.info(f"Subscribing to new topic: {topic_name}")
            subscription = await self.pubsub.subscribe(topic_name)
            self.subscriptions[topic_name] = subscription
            logger.info(f"Successfully subscribed to topic: {topic_name}")
            self._log_system_message(f"Subscribed to topic: {topic_name}")
            
            # Add to topic_handlers list - will be started in start_message_handlers
            self.topic_handlers.append((topic_name, subscription))
            logger.info(f"Added handler for topic: {topic_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe to topic {topic_name}: {e}")
            self._log_system_message(f"ERROR: Failed to subscribe to topic {topic_name}: {e}")
            return False
