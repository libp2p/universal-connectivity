"""
GossipSub implementation for py-peer.
"""
from typing import List, Any, Dict

from libp2p.custom_types import TProtocol
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub
from libp2p.host.host_interface import IHost

from py_peer.config import GOSSIPSUB_PROTOCOL_ID
from py_peer.utils.logging import get_logger

logger = get_logger(__name__)


def create_gossipsub(
    protocols: List[TProtocol] = None,
    degree: int = 3,
    degree_low: int = 2,
    degree_high: int = 4,
    time_to_live: int = 60,
    gossip_window: int = 2,
    gossip_history: int = 5,
    heartbeat_initial_delay: float = 2.0,
    heartbeat_interval: float = 5.0,
) -> GossipSub:
    """
    Create a GossipSub instance with the given parameters.
    
    Args:
        protocols: List of protocols to use
        degree: Number of peers to maintain in mesh
        degree_low: Lower bound for mesh peers
        degree_high: Upper bound for mesh peers
        time_to_live: TTL for message cache in seconds
        gossip_window: Window for gossip
        gossip_history: History length to keep
        heartbeat_initial_delay: Initial delay for heartbeats
        heartbeat_interval: Interval between heartbeats
        
    Returns:
        A GossipSub instance
    """
    if protocols is None:
        protocols = [GOSSIPSUB_PROTOCOL_ID]
    
    return GossipSub(
        protocols=protocols,
        degree=degree,
        degree_low=degree_low,
        degree_high=degree_high,
        time_to_live=time_to_live,
        gossip_window=gossip_window,
        gossip_history=gossip_history,
        heartbeat_initial_delay=heartbeat_initial_delay,
        heartbeat_interval=heartbeat_interval,
    )


def create_pubsub(host: IHost, gossipsub: GossipSub) -> Pubsub:
    """
    Create a Pubsub instance with the given host and GossipSub router.
    
    Args:
        host: The libp2p host
        gossipsub: The GossipSub router
        
    Returns:
        A Pubsub instance
    """
    return Pubsub(host, gossipsub)