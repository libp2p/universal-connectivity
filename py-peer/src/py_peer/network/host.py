"""
Host creation and management for py-peer.
"""
import multiaddr
from typing import List, Dict, Any

from libp2p import new_host
from libp2p.crypto.keys import KeyPair
from libp2p.custom_types import TProtocol
from libp2p.stream_muxer.mplex.mplex import Mplex
from libp2p.tools.factories import security_options_factory_factory
from libp2p.host.host_interface import IHost

from py_peer.config import NOISE_PROTOCOL_ID, MPLEX_PROTOCOL_ID
from py_peer.utils.logging import get_logger

logger = get_logger(__name__)


def create_host(
    key_pair: KeyPair,
    listen_addrs: List[multiaddr.Multiaddr] = None,
    security_protocol: TProtocol = NOISE_PROTOCOL_ID,
    muxer_protocol: TProtocol = MPLEX_PROTOCOL_ID,
) -> IHost:
    """
    Create a new libp2p host.
    
    Args:
        key_pair: The key pair for the host
        listen_addrs: List of multiaddresses to listen on
        security_protocol: The security protocol to use
        muxer_protocol: The stream multiplexer protocol to use
        
    Returns:
        A new libp2p host
    """
    if listen_addrs is None:
        listen_addrs = []
    
    # Security options
    security_options_factory = security_options_factory_factory(security_protocol)
    security_options = security_options_factory(key_pair)
    
    # Create a new libp2p host
    host = new_host(
        key_pair=key_pair,
        muxer_opt={muxer_protocol: Mplex},
        sec_opt=security_options,
    )
    
    logger.debug(f"Host ID: {host.get_id()}")
    logger.debug(
        f"Host multiselect protocols: "
        f"{host.get_mux().get_protocols() if hasattr(host, 'get_mux') else 'N/A'}"
    )
    
    return host


def get_listen_multiaddr(port: int) -> multiaddr.Multiaddr:
    """
    Get a multiaddress for listening on all interfaces with the given port.
    
    Args:
        port: The port to listen on
        
    Returns:
        A multiaddress
    """
    return multiaddr.Multiaddr(f"/ip4/0.0.0.0/tcp/{port}")