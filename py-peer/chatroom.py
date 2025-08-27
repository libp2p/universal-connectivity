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
    
    def __init__(self, host: BasicHost, pubsub: Pubsub, nickname: str, multiaddr: str = None):
        self.host = host
        self.pubsub = pubsub
        self.nickname = nickname
        self.peer_id = str(host.get_id())
        self.multiaddr = multiaddr or f"unknown/{self.peer_id}"
        
        # Subscriptions
        self.chat_subscription = None
        self.discovery_subscription = None
        
        # Message handlers
        self.message_handlers = []
        self.system_message_handlers = []
        
        # Running state
        self.running = False
        
        logger.info(f"ChatRoom initialized for peer {self.peer_id[:8]}... with nickname '{nickname}'")
        self._log_system_message("Universal Connectivity Chat Started")
        self._log_system_message(f"Nickname: {nickname}")
        self._log_system_message(f"Multiaddr: {self.multiaddr}")
        self._log_system_message("Commands: /quit, /peers, /status, /multiaddr")
    
    def _log_system_message(self, message: str):
        """Log system message to file."""
        system_logger.info(message)
    
    @classmethod
    async def join_chat_room(cls, host: BasicHost, pubsub: Pubsub, nickname: str, multiaddr: str = None) -> "ChatRoom":
        """Create and join a chat room."""
        chat_room = cls(host, pubsub, nickname, multiaddr)
        await chat_room._subscribe_to_topics()
        chat_room._log_system_message(f"Joined chat room as '{nickname}'")
        return chat_room
    
    async def _subscribe_to_topics(self):
        """Subscribe to all necessary topics."""
        try:
            # Subscribe to chat topic
            self.chat_subscription = await self.pubsub.subscribe(CHAT_TOPIC)
            logger.info(f"Subscribed to chat topic: {CHAT_TOPIC}")
            
            # Subscribe to discovery topic
            self.discovery_subscription = await self.pubsub.subscribe(PUBSUB_DISCOVERY_TOPIC)
            logger.info(f"Subscribed to discovery topic: {PUBSUB_DISCOVERY_TOPIC}")
            
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
            
            # Send plain text message (Go-compatible format)
            print(f"Sending message {message}")
            await self.pubsub.publish(CHAT_TOPIC, message.encode())
            logger.info(f"✅ Message published successfully to topic '{CHAT_TOPIC}'")
            
            if peer_count == 0:
                print(f"⚠️  No peers connected - message sent to topic but no one will receive it")
            else:
                print(f"✓ Message sent to {peer_count} peer(s)")
                
        except Exception as e:
            logger.error(f"❌ Failed to publish message: {e}")
            print(f"❌ Error sending message: {e}")
            self._log_system_message(f"ERROR: Failed to publish message: {e}")
    
    async def _handle_chat_messages(self):
        """Handle incoming chat messages in Go-compatible format."""
        logger.debug("📨 Starting chat message handler")
        
        try:
            async for message in self._message_stream(self.chat_subscription):
                try:
                    # Handle plain text messages (common format with Go peer)
                    raw_data = message.data.decode()
                    sender_id = base58.b58encode(message.from_id).decode() if message.from_id else "unknown"
                    
                    # Use simple format - plain text messages with short sender ID as nickname
                    sender_nick = sender_id[-8:] if len(sender_id) > 8 else sender_id
                    actual_message = raw_data
                    
                    logger.info(f"📨 Received message from {sender_id} ({sender_nick}): {actual_message}")
                    
                    # Create ChatMessage object for handlers
                    chat_msg = ChatMessage(
                        message=actual_message,
                        sender_id=sender_id,
                        sender_nick=sender_nick
                    )
                    
                    # Call message handlers
                    for handler in self.message_handlers:
                        try:
                            await handler(chat_msg)
                        except Exception as e:
                            logger.error(f"❌ Error in message handler: {e}")
                    
                    # Default console output if no handlers
                    if not self.message_handlers:
                        print(f"[{chat_msg.sender_nick}]: {chat_msg.message}")
                
                except Exception as e:
                    logger.error(f"❌ Error processing chat message: {e}")
        
        except Exception as e:
            logger.error(f"❌ Error in chat message handler: {e}")
    
    async def _handle_discovery_messages(self):
        """Handle incoming discovery messages."""
        logger.debug("Starting discovery message handler")
        
        try:
            async for message in self._message_stream(self.discovery_subscription):
                try:
                    # Handle discovery message (simplified - just log for now)
                    sender_id = base58.b58encode(message.from_id).decode() if message.from_id else "unknown"
                    
                    # Skip our own messages
                    if sender_id == self.peer_id:
                        continue
                    
                    logger.info(f"Discovery message from peer: {sender_id}")
                
                except Exception as e:
                    logger.error(f"Error processing discovery message: {e}")
        
        except Exception as e:
            logger.error(f"Error in discovery message handler: {e}")
    
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
            nursery.start_soon(self._handle_chat_messages)
            nursery.start_soon(self._handle_discovery_messages)
    
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
                        print(f"📊 Status:")
                        print(f"  - Multiaddr: {self.multiaddr}")
                        print(f"  - Nickname: {self.nickname}")
                        print(f"  - Connected peers: {peer_count}")
                        print(f"  - Subscribed topics: chat, discovery")
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
