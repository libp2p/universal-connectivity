"""
ChatRoom module for Universal Connectivity Python Peer

This module handles chat room functionality including message handling,
pubsub subscriptions, and peer discovery.
"""

from __future__ import annotations

import base58
import json
import logging
import os
import threading
import time
import trio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from typing import Any, Set

from libp2p.abc import IHost, ISubscriptionAPI
from libp2p.crypto.serialization import deserialize_public_key
from libp2p.peer.id import ID
from libp2p.pubsub.pb.rpc_pb2 import Message
from libp2p.pubsub.pubsub import Pubsub
from multiaddr import Multiaddr

from core.pb import Peer as DiscoveredPeer

logger = logging.getLogger("chatroom")

# Separate logger for the human-readable system log. The file location is
# configured at startup (data directory) rather than at import time, so running
# the peer never drops a system_messages.txt into the current directory.
SYSTEM_LOG_MAX_BYTES = 1_000_000
SYSTEM_LOG_BACKUPS = 3

system_logger = logging.getLogger("system_messages")
system_logger.setLevel(logging.INFO)
system_logger.propagate = False  # Don't send to parent loggers
system_logger.addHandler(logging.NullHandler())

# Absolute path of the active rotating log file, or None when disabled.
system_log_path: str | None = None


def configure_system_log(path: str | os.PathLike[str] | None = None) -> str | None:
    """Send system messages to a rotating file at ``path``.

    Called by the runtime once the data directory is known. Idempotent: an
    existing rotating handler is replaced instead of stacked, so tests and
    repeated runtimes keep exactly one file sink. Returns the active path, or
    ``None`` when the log is disabled because no path was given or the handler
    could not be created (for example an unwritable directory).
    """
    global system_log_path

    for handler in list(system_logger.handlers):
        if isinstance(handler, RotatingFileHandler):
            system_logger.removeHandler(handler)
            handler.close()
    system_log_path = None

    if path is None:
        return None

    target = os.path.abspath(os.path.expanduser(str(path)))
    try:
        directory = os.path.dirname(target)
        if directory:
            os.makedirs(directory, exist_ok=True)
        handler = RotatingFileHandler(
            target,
            mode="a",
            maxBytes=SYSTEM_LOG_MAX_BYTES,
            backupCount=SYSTEM_LOG_BACKUPS,
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning(f"System log disabled at {target}: {exc}")
        return None

    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
    )
    system_logger.addHandler(handler)
    system_log_path = target
    return target

# Chat room buffer size for incoming messages
CHAT_ROOM_BUF_SIZE = 128

# Topics used in the chat system
PUBSUB_DISCOVERY_TOPIC = "universal-connectivity-browser-peer-discovery"
PROFILE_TOPIC = "universal-connectivity-profiles"
CHAT_TOPIC = "universal-connectivity"

# Topics that are part of the protocol but are not user-facing chat channels.
# The discovery topic carries protobuf peer/WebRTC announcements from browser
# peers; the profile topic carries nickname announcements between Python
# peers. Treating either as chat would expose protocol payloads as messages.
NON_CHAT_TOPICS = {PUBSUB_DISCOVERY_TOPIC, PROFILE_TOPIC}

# Guardrails against a client creating unlimited channels.
MAX_TOPIC_NAME_LENGTH = 128
MAX_TOPICS = 100


def _snapshot_keys(mapping: Mapping[Any, Any], attempts: int = 3) -> list[str]:
    """
    Copy a dict's keys from a thread that does not own the dict.

    ``pubsub.peers`` and ``ChatRoom.subscriptions`` are mutated by the trio
    thread while Tornado handlers read them. A plain ``list(mapping)`` can
    raise RuntimeError("dictionary changed size during iteration") if the dict
    changes size mid-copy, so retry the cheap snapshot instead of leaking a
    500 to the API client. Only the specific "changed size" RuntimeError is
    swallowed; unrelated RuntimeErrors propagate normally.
    """
    _CHANGED = "changed size during iteration"
    for _ in range(attempts):
        try:
            return [str(key) for key in mapping.keys()]
        except RuntimeError as exc:
            if _CHANGED not in str(exc):
                raise
            continue
    logger.warning(
        "_snapshot_keys: dict mutated on every attempt (%d); returning empty list",
        attempts,
    )
    return []


@dataclass
class ChatMessage:
    """Represents a chat message."""
    message: str
    sender_id: str
    sender_nick: str
    topic: str | None = None  # Topic the message was received on
    timestamp: float = field(default_factory=time.time)
    message_id: str | None = None


class ChatRoom:
    """
    Represents a subscription to PubSub topics for chat functionality.
    Messages can be published to topics and received messages are handled
    through callback functions.
    """

    def __init__(
        self,
        host: IHost,
        pubsub: Pubsub,
        nickname: str,
        multiaddr: str | None = None,
        headless_service: Any = None,
        topic: str | None = None,
    ):
        self.host = host
        self.pubsub = pubsub
        self.nickname = nickname
        self.peer_id = str(host.get_id())
        self.multiaddr = multiaddr or f"unknown/{self.peer_id}"
        self.headless_service = headless_service  # Reference for identify protocol

        # Use custom topic if provided, otherwise use default
        self.chat_topic = topic if topic else CHAT_TOPIC
        if self.chat_topic in NON_CHAT_TOPICS:
            raise ValueError(
                f"Topic '{self.chat_topic}' is reserved for peer discovery "
                "and cannot be used as the chat topic."
            )

        # Subscriptions - now a dictionary to track all subscriptions
        self.subscriptions: dict[str, ISubscriptionAPI] = {}
        self.chat_subscription: ISubscriptionAPI | None = None
        self.discovery_subscription: ISubscriptionAPI | None = None
        self.profile_subscription: ISubscriptionAPI | None = None
        self.peer_nicknames: dict[str, str] = {}
        self._nickname_lock = threading.RLock()

        # Message handlers
        self.message_handlers: list[
            Callable[[ChatMessage], Awaitable[None]]
        ] = []
        self.system_message_handlers: list[
            Callable[[str], Awaitable[None]]
        ] = []

        # Topic handlers - stores (topic_name, subscription) for dynamic topics
        self.topic_handlers: list[tuple[str, ISubscriptionAPI]] = []
        self.active_topic_handlers: set[str] = set()

        # Running state
        self.running = False
        self.nursery: trio.Nursery | None = None

        logger.info(f"ChatRoom initialized for peer {self.peer_id[:8]}... with nickname '{nickname}'")
        logger.info(f"Chat topic: {self.chat_topic}")
        self._log_system_message("Universal Connectivity Chat Started")
        self._log_system_message(f"Nickname: {nickname}")
        self._log_system_message(f"Topic: {self.chat_topic}")
        self._log_system_message(f"Multiaddr: {self.multiaddr}")
        self._log_system_message("Commands: /quit, /peers, /status, /multiaddr")

    def _log_system_message(self, message: str) -> None:
        """Log system message to file."""
        system_logger.info(message)

    @classmethod
    async def join_chat_room(
        cls,
        host: IHost,
        pubsub: Pubsub,
        nickname: str,
        multiaddr: str | None = None,
        headless_service: Any = None,
        topic: str | None = None,
    ) -> ChatRoom:
        """Create and join a chat room."""
        chat_room = cls(host, pubsub, nickname, multiaddr, headless_service, topic)
        await chat_room._subscribe_to_topics()
        await chat_room.announce_profile()
        await chat_room.announce_discovery()
        chat_room._log_system_message(f"Joined chat room as '{nickname}'")
        return chat_room

    async def _subscribe_to_topics(self) -> None:
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

            # Protocol-only topic for exchanging nicknames between Python peers.
            # Browser peers ignore it; chat framing remains unchanged.
            self.profile_subscription = await self.pubsub.subscribe(PROFILE_TOPIC)
            self.subscriptions[PROFILE_TOPIC] = self.profile_subscription
            self.topic_handlers.append((PROFILE_TOPIC, self.profile_subscription))
            logger.info(f"Subscribed to profile topic: {PROFILE_TOPIC}")

        except Exception as e:
            logger.error(f"Failed to subscribe to topics: {e}")
            self._log_system_message(f"ERROR: Failed to subscribe to topics: {e}")
            raise

    async def publish_message(self, message: str) -> None:
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

    async def publish_to_topic(self, topic: str, message: str) -> bool:
        """Publish a message to a specific topic."""
        try:
            # The discovery topic is a protocol channel, not a chat channel.
            if topic in NON_CHAT_TOPICS:
                logger.warning(f"Refusing to publish chat to reserved topic: {topic}")
                return False

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

    async def _validate_message_with_identify(
        self, message: Message, sender_id: str
    ) -> bool:
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

    async def _handle_topic_messages(
        self, topic_name: str, subscription: ISubscriptionAPI
    ) -> None:
        """Handle incoming messages for chat topics; drain protocol topics."""
        logger.debug(f"📨 Starting message handler for topic: {topic_name}")

        if topic_name == PROFILE_TOPIC:
            async for message in self._message_stream(subscription):
                try:
                    payload = json.loads(message.data.decode())
                    if not isinstance(payload, dict):
                        continue
                    nickname = payload.get("nickname")
                    if not isinstance(nickname, str):
                        continue
                    nickname = nickname.strip()
                    if not nickname or len(nickname) > 64:
                        continue
                    sender_id = (
                        base58.b58encode(message.from_id).decode()
                        if message.from_id
                        else payload.get("peer_id")
                    )
                    if not sender_id or sender_id == self.peer_id:
                        continue
                    with self._nickname_lock:
                        self.peer_nicknames[str(sender_id)] = nickname
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
            return

        if topic_name == PUBSUB_DISCOVERY_TOPIC:
            await self._handle_discovery_messages(subscription)
            return

        if topic_name in NON_CHAT_TOPICS:
            # Drain any other non-chat protocol topics so subscription buffer does not fill.
            async for _message in self._message_stream(subscription):
                continue
            return

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

                    # Use the libp2p sequence number as the stable wire id.
                    # Re-delivery of the same frame must collapse in storage.
                    seqno = getattr(message, "seqno", None)
                    message_id = None
                    if seqno:
                        if isinstance(seqno, bytes):
                            seqno = seqno.hex()
                        message_id = f"{topic_name}:{sender_id}:{seqno}"

                    # Format sender nickname; profiles are exchanged on the
                    # protocol-only profile topic.
                    if is_own_message:
                        sender_nick = self.nickname
                    else:
                        sender_nick = self.get_peer_nickname(sender_id) or (
                            sender_id[-8:] if len(sender_id) > 8 else sender_id
                        )

                    actual_message = raw_data

                    logger.info(f"📨 Received message on topic '{topic_name}' from {sender_id} ({sender_nick}): {actual_message}")

                    # Create ChatMessage object for handlers
                    chat_msg = ChatMessage(
                        message=actual_message,
                        sender_id=sender_id,
                        sender_nick=sender_nick,
                        topic=topic_name,
                        message_id=message_id,
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

    async def _handle_discovery_messages(
        self, subscription: ISubscriptionAPI
    ) -> None:
        """Process peer discovery announcements from browser and desktop peers."""
        logger.info(f"📡 Starting discovery listener on {PUBSUB_DISCOVERY_TOPIC}")
        async for message in self._message_stream(subscription):
            try:
                peer_msg = DiscoveredPeer()
                peer_msg.ParseFromString(message.data)

                if not peer_msg.publicKey:
                    continue

                try:
                    pub_obj = deserialize_public_key(peer_msg.publicKey)
                    peer_id = ID.from_pubkey(pub_obj)
                except Exception as exc:
                    logger.debug(f"Failed to deserialize discovery public key: {exc}")
                    continue

                pid_str = str(peer_id)
                if pid_str == str(self.peer_id):
                    continue

                discovered_addrs: list[Multiaddr] = []
                for raw_addr in peer_msg.multiAddrs:
                    try:
                        m = Multiaddr(raw_addr)
                        discovered_addrs.append(m)
                    except Exception:
                        try:
                            m = Multiaddr(raw_addr.decode("utf-8"))
                            discovered_addrs.append(m)
                        except Exception:
                            continue

                if not discovered_addrs:
                    continue

                peerstore = self.host.get_peerstore()
                try:
                    peerstore.add_pubkey(peer_id, pub_obj)
                except Exception:
                    pass
                try:
                    peerstore.add_addrs(peer_id, discovered_addrs, ttl=3600)
                except Exception:
                    pass

                logger.info(
                    f"🧭 Discovered peer {pid_str} via PubSub with {len(discovered_addrs)} addrs"
                )

                # Connect if not currently connected
                connected_peers = {
                    str(p) for p in self.host.get_connected_peers()
                }
                if pid_str not in connected_peers and discovered_addrs:
                    # Sort to prioritize non-loopback addresses
                    sorted_addrs = sorted(
                        discovered_addrs,
                        key=lambda a: (
                            1 if "/ip4/127." in str(a) or "/ip6/::1" in str(a)
                            else 0
                        ),
                    )
                    best_addr = sorted_addrs[0]
                    addr_str = str(best_addr)
                    if f"/p2p/{pid_str}" not in addr_str:
                        addr_str = f"{addr_str}/p2p/{pid_str}"
                    if getattr(self, "headless_service", None):
                        self.headless_service.connect_to_peer(addr_str)
            except Exception as e:
                logger.debug(f"Error handling discovery message: {e}")

    async def _message_stream(
        self, subscription: ISubscriptionAPI
    ) -> AsyncIterator[Message]:
        """Create an async iterator for subscription messages."""
        while self.running:
            try:
                message = await subscription.get()
                yield message
            except Exception as e:
                logger.error(f"Error getting message from subscription: {e}")
                await trio.sleep(1)  # Avoid tight loop on error

    async def start_message_handlers(self) -> None:
        """Start all message handler tasks."""
        self.running = True

        async with trio.open_nursery() as nursery:
            # Store nursery reference for dynamic task spawning
            self.nursery = nursery

            # Start background task to monitor for new topic subscriptions
            nursery.start_soon(self._monitor_new_topics)

            # Start background task to periodically broadcast peer discovery
            nursery.start_soon(self._discovery_announcer_loop)

    async def _monitor_new_topics(self) -> None:
        """Monitor for new topic subscriptions and start handlers for them."""
        nursery = self.nursery
        if nursery is None:
            logger.error("Cannot monitor topics before the nursery is created")
            return
        while self.running:
            try:
                # Check if there are any new topics that need handlers
                for topic_name, subscription in self.topic_handlers:
                    if topic_name not in self.active_topic_handlers:
                        logger.info(f"Starting message handler for topic: {topic_name}")

                        # Use generic handler for all topics (including chat and discovery)
                        nursery.start_soon(self._handle_topic_messages, topic_name, subscription)
                        self.active_topic_handlers.add(topic_name)

                # Check periodically (every 0.5 seconds)
                await trio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error in topic monitor: {e}")
                await trio.sleep(1)

    def add_message_handler(
        self, handler: Callable[[ChatMessage], Awaitable[None]]
    ) -> None:
        """Add a custom message handler."""
        self.message_handlers.append(handler)

    def add_system_message_handler(
        self, handler: Callable[[str], Awaitable[None]]
    ) -> None:
        """Add a custom system message handler."""
        self.system_message_handlers.append(handler)

    async def run_interactive(self) -> None:
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

    async def _input_handler(self) -> None:
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

    async def stop(self) -> None:
        """Stop the chat room."""
        self.running = False
        if self.nursery is not None:
            self.nursery.cancel_scope.cancel()
        logger.info("ChatRoom stopped")

    def get_connected_peers(self) -> Set[str]:
        """Get a snapshot of connected peer IDs."""
        return {str(peer_id) for peer_id in _snapshot_keys(self.pubsub.peers)}

    def get_peer_count(self) -> int:
        """Get number of connected peers."""
        return len(self.pubsub.peers)

    async def announce_profile(self) -> None:
        """Publish this peer's nickname on the protocol-only profile topic."""
        try:
            payload = json.dumps(
                {"peer_id": self.peer_id, "nickname": self.nickname}
            ).encode()
            await self.pubsub.publish(PROFILE_TOPIC, payload)
        except Exception:
            logger.debug("Could not announce peer profile", exc_info=True)

    async def announce_discovery(self) -> None:
        """Publish this peer's public key and addresses to the discovery topic."""
        try:
            peer_msg = DiscoveredPeer()
            pub_key = self.host.get_public_key()
            peer_msg.publicKey = pub_key.serialize()

            # Gather listen and advertised addresses
            addrs = list(self.host.get_addrs())
            if getattr(self, "headless_service", None):
                for full_maddr in getattr(
                    self.headless_service, "full_multiaddrs", []
                ):
                    try:
                        clean_str = str(full_maddr).split("/p2p/")[0]
                        clean_maddr = Multiaddr(clean_str)
                        if clean_maddr not in addrs:
                            addrs.append(clean_maddr)
                    except Exception:
                        pass

            for addr in addrs:
                try:
                    peer_msg.multiAddrs.append(addr.to_bytes())
                except Exception:
                    pass

            payload = peer_msg.SerializeToString()
            await self.pubsub.publish(PUBSUB_DISCOVERY_TOPIC, payload)
            logger.debug(
                f"📢 Published peer discovery announcement with {len(addrs)} addrs"
            )
        except Exception as exc:
            logger.debug(f"Could not announce peer discovery: {exc}")

    async def _discovery_announcer_loop(self) -> None:
        """Periodically broadcast peer announcement on the discovery topic."""
        logger.info("📡 Starting periodic discovery announcer loop (interval 10s)")
        while self.running:
            try:
                await trio.sleep(10)
                if not self.running:
                    break
                await self.announce_discovery()
            except trio.Cancelled:
                break
            except Exception as e:
                logger.debug(f"Discovery announcer loop error: {e}")

    def get_peer_nickname(self, peer_id: str) -> str | None:
        """Return a cached remote nickname, if one has been announced."""
        with self._nickname_lock:
            return self.peer_nicknames.get(peer_id)

    def get_subscribed_topics(self) -> Set[str]:
        """Get user-facing (chat) subscriptions, excluding protocol topics."""
        return {
            topic
            for topic in _snapshot_keys(self.subscriptions)
            if topic not in NON_CHAT_TOPICS
        }

    def get_all_subscriptions(self) -> Set[str]:
        """Get every pubsub subscription, including protocol-only topics."""
        return set(_snapshot_keys(self.subscriptions))

    async def subscribe_to_topic(self, topic_name: str) -> bool:
        """
        Subscribe to a new topic dynamically.

        Args:
            topic_name: The name of the topic to subscribe to

        Returns:
            True if subscription was successful, False otherwise
        """
        try:
            if not isinstance(topic_name, str) or not topic_name:
                logger.warning("Refusing to subscribe to an empty/non-string topic")
                return False
            if len(topic_name) > MAX_TOPIC_NAME_LENGTH:
                logger.warning(
                    f"Refusing to subscribe to oversized topic "
                    f"({len(topic_name)} > {MAX_TOPIC_NAME_LENGTH} chars)"
                )
                return False
            if topic_name in NON_CHAT_TOPICS:
                logger.warning(f"Refusing to subscribe to reserved topic: {topic_name}")
                return False
            if topic_name in self.subscriptions:
                logger.warning(f"Already subscribed to topic: {topic_name}")
                return False
            if len(self.get_subscribed_topics()) >= MAX_TOPICS:
                logger.warning(f"Refusing topic subscription: limit {MAX_TOPICS} reached")
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
