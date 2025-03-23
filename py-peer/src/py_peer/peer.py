"""
Core peer implementation for py-peer.
"""
import multiaddr
import trio
from typing import Optional, List, Dict, Any, Set
import logging

from libp2p.tools.async_service.trio_service import background_trio_service
from libp2p.pubsub.pubsub import ISubscriptionAPI

from py_peer.config import PeerConfig
from py_peer.network.host import create_host, get_listen_multiaddr
from py_peer.network.discovery import connect_to_peer, monitor_peers
from py_peer.pubsub.gossipsub import create_gossipsub, create_pubsub
from py_peer.pubsub.handlers import receive_loop, publish_loop, monitor_peer_topics
from py_peer.utils.logging import get_logger

logger = get_logger(__name__)


class Peer:
    """A libp2p peer with pubsub capabilities."""
    
    def __init__(self, config: PeerConfig):
        """
        Initialize a new peer.
        
        Args:
            config: The peer configuration
        """
        self.config = config
        self.host = None
        self.pubsub = None
        self.gossipsub = None
        self.subscriptions: Dict[str, Any] = {}
        
    async def start(self) -> None:
        """Start the peer and all its services."""
        # Create the host
        listen_addr = get_listen_multiaddr(self.config.port)
        self.host = create_host(self.config.key_pair)
        
        # Create gossipsub and pubsub
        self.gossipsub = create_gossipsub()
        self.pubsub = create_pubsub(self.host, self.gossipsub)
        
        # Start the host and services
        async with self.host.run(listen_addrs=[listen_addr]), trio.open_nursery() as nursery:
            logger.info(f"Node started with peer ID: {self.host.get_id()}")
            logger.info(f"Listening on: {listen_addr}")
            logger.info("Initializing PubSub and GossipSub...")
            
            # Start pubsub and gossipsub services
            async with background_trio_service(self.pubsub):
                async with background_trio_service(self.gossipsub):
                    logger.info("Pubsub and GossipSub services started.")
                    await self.pubsub.wait_until_ready()
                    logger.info("Pubsub ready.")
                    
                    # Subscribe to the configured topic
                    await self.subscribe_to_topic(self.config.topic, nursery)
                    
                    # Connect to destination if specified
                    if self.config.destination:
                        await self.connect_to_destination(nursery)
                    else:
                        # Server mode
                        logger.info(
                            "Run this script in another console with:\n"
                            f"python main.py "
                            f"-d /ip4/127.0.0.1/tcp/{self.config.port}/p2p/{self.host.get_id()}\n"
                        )
                        logger.info("Waiting for peers...")
                        
                        # Start topic monitoring to auto-subscribe to client topics
                        nursery.start_soon(
                            monitor_peer_topics, 
                            self.pubsub, 
                            self.handle_new_topic
                        )
                    
                    # Start the publish loop for the main topic
                    nursery.start_soon(publish_loop, self.pubsub, self.config.topic)
                    
                    # Monitor peers
                    nursery.start_soon(monitor_peers, self.pubsub)
                    
                    # Keep the peer running
                    await trio.sleep_forever()
    
    async def subscribe_to_topic(self, topic: str, nursery: trio.Nursery) -> None:
        """
        Subscribe to a topic and start a receive loop.
        
        Args:
            topic: The topic to subscribe to
            nursery: The trio nursery
        """
        logger.info(f"Subscribing to topic: {topic}")
        subscription = await self.pubsub.subscribe(topic)
        self.subscriptions[topic] = subscription
        
        # Start a receive loop for this topic
        nursery.start_soon(receive_loop, subscription)
    
    async def handle_new_topic(self, topic: str, subscription: ISubscriptionAPI) -> None:
        """
        Handle a new topic discovered from peers.
        
        Args:
            topic: The new topic
            subscription: The subscription to the topic
        """
        self.subscriptions[topic] = subscription
        logger.info(f"Added new topic to subscriptions: {topic}")
    
    async def connect_to_destination(self, nursery: trio.Nursery) -> None:
        """
        Connect to the destination peer.
        
        Args:
            nursery: The trio nursery
        """
        if not self.config.destination:
            return
        
        success = await connect_to_peer(self.host, self.config.destination)
        if not success:
            logger.error("Failed to connect to destination peer. Exiting.")
            return
        
        # Debug peer connections
        if logger.isEnabledFor(logging.DEBUG):
            await trio.sleep(1)
            logger.debug(f"After connection, pubsub.peers: {self.pubsub.peers}")
            peer_protocols = [
                self.gossipsub.peer_protocol.get(p)
                for p in self.pubsub.peers.keys()
            ]
            logger.debug(f"Peer protocols: {peer_protocols}")