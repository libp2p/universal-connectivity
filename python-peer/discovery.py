import asyncio
import json
import logging
import time
from typing import List, Dict, Any

logger = logging.getLogger("app")

async def setup_discovery(node, service_tag: str) -> None:
    """
    Set up mDNS discovery for local peer finding.
    
    Args:
        node: The libp2p node
        service_tag: The service tag for discovery
    """
    try:
        await node.setup_mdns(service_tag)
        logger.info(f"mDNS discovery set up with service tag: {service_tag}")
    except Exception as e:
        logger.error(f"Failed to set up mDNS discovery: {e}")

class DiscoveryNotifee:
    """
    Notification handler for peer discovery events.
    """
    def __init__(self, node):
        self.node = node
    
    async def peer_discovered(self, peer_info):
        """Handle peer discovery events."""
        peer_id = peer_info.get("id")
        addrs = peer_info.get("addrs", [])
        
        if not peer_id or not addrs:
            return
        
        logger.info(f"Discovered peer: {peer_id}")
        
        # Skip if it's our own peer ID
        if peer_id == str(self.node.get_id()):
            return
        
        # Try to connect if not already connected
        if not self.node.is_connected(peer_id):
            for addr in addrs:
                try:
                    await self.node.connect(f"{addr}/p2p/{peer_id}")
                    logger.info(f"Connected to discovered peer: {peer_id}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to connect to {peer_id} at {addr}: {e}")

async def discover_peers(node, service_tag: str) -> None:
    """
    Actively discover peers using DHT and other mechanisms.
    
    Args:
        node: The libp2p node
        service_tag: The service tag for discovery
    """
    # Set up a notifee for discovery events
    notifee = DiscoveryNotifee(node)
    
    # Register for peer discovery events
    if hasattr(node, "on_peer_discovered"):
        node.on_peer_discovered(notifee.peer_discovered)
    
    # Periodically announce our presence to the discovery topic
    pubsub_discovery_topic = "universal-connectivity-browser-peer-discovery"
    
    while True:
        try:
            # Announce our addrs to the discovery topic
            addrs = [str(addr) for addr in node.get_addrs()]
            
            announce_msg = json.dumps({
                "peer_id": str(node.get_id()),
                "addrs": addrs,
                "timestamp": time.time()
            })
            
            # Publish to the discovery topic if we have a pubsub
            if hasattr(node, "pubsub") and node.pubsub:
                await node.pubsub.publish(pubsub_discovery_topic, announce_msg.encode('utf-8'))
                logger.debug(f"Published discovery announcement: {announce_msg}")
            
            # Use Kademlia DHT for discovery if available
            if hasattr(node, "dht") and node.dht:
                try:
                    # Advertise our presence
                    await node.dht.provide(service_tag.encode('utf-8'))
                    
                    # Find other peers
                    peers = await node.dht.find_providers(service_tag.encode('utf-8'))
                    
                    for peer in peers:
                        if peer.get("id") == str(node.get_id()):
                            continue
                        
                        await notifee.peer_discovered(peer)
                except Exception as e:
                    logger.error(f"DHT discovery error: {e}")
            
            # Wait before next announcement
            await asyncio.sleep(60)  # Announce every minute
            
        except asyncio.CancelledError:
            logger.info("Discovery task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in discover_peers: {e}")
            await asyncio.sleep(30)  # Back off on errors