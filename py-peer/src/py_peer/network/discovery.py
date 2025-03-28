"""
Peer discovery mechanisms for py-peer.
"""
import multiaddr
import trio

from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.host.host_interface import (
    IHost,
)
from libp2p.pubsub.pubsub import Pubsub

from py_peer.utils.logging import get_logger

logger = get_logger(__name__)


async def connect_to_peer(host: IHost, peer_addr: str) -> bool:
    """
    Connect to a peer using its multiaddress.
    
    Args:
        host: The libp2p host
        peer_addr: The multiaddress of the peer to connect to
        
    Returns:
        True if connection was successful, False otherwise
    """
    try:
        maddr = multiaddr.Multiaddr(peer_addr)
        protocols_in_maddr = maddr.protocols()
        info = info_from_p2p_addr(maddr)
        
        logger.debug(f"Multiaddr protocols: {protocols_in_maddr}")
        logger.info(
            f"Connecting to peer: {info.peer_id} "
            f"using protocols: {protocols_in_maddr}"
        )
        
        await host.connect(info)
        logger.info(f"Connected to peer: {info.peer_id}")
        return True
    except Exception:
        logger.exception(f"Failed to connect to peer: {peer_addr}")
        return False


async def monitor_peers(pubsub: Pubsub, interval: float = 30.0) -> None:
    """
    Monitor connected peers and log information periodically.
    
    Args:
        host: The libp2p host
        interval: The interval in seconds between checks
    """
    while True:
        # peers = host.get_network().get_peer_id()
        peers = pubsub.peers
        logger.debug(f"Connected to {len(peers)} peers: {peers}")
        await trio.sleep(interval)