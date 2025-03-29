import logging
from typing import Dict, Any, List

from libp2p.crypto.keys import PrivateKey
from libp2p.security.noise.transport import NoiseTransport
from libp2p.security.secio import SecioTransport
from libp2p.stream_muxer.mplex.mplex import MPLEXStreamMuxer
from libp2p.stream_muxer.yamux.yamux import YAMUXStreamMuxer
from libp2p.transport.tcp.tcp import TCPTransport
from libp2p.transport.upgrader import TransportUpgrader
from libp2p.relay.circuit.transport import CircuitRelay

logger = logging.getLogger("app")

def create_node_config(private_key: PrivateKey) -> Dict[str, Any]:
    """
    Create and return a configuration dictionary for a libp2p node.
    
    Args:
        private_key: The node's private key for identity
        
    Returns:
        Dict[str, Any]: Configuration dictionary for libp2p node creation
    """
    # Define listening addresses
    listen_addrs = [
        "/ip4/0.0.0.0/tcp/9095",  # TCP for general connectivity
        "/ip6/::/tcp/9095",       # IPv6 TCP
    ]
    
    # Create the node configuration
    return {
        "identity": private_key,
        "listen_addrs": listen_addrs,
        
        # Transport configuration
        "transport_opt": {
            "transports": [
                TCPTransport(),
                # Add WebRTC later when Python implementation is available
                # Add QUIC later when Python implementation is available
            ]
        },
        
        # Security configuration - security transport modules
        "security_opt": {
            "security_transports": [
                NoiseTransport(),  # Noise protocol for encryption
                SecioTransport(),  # Fallback security transport
            ]
        },
        
        # Stream muxer configuration
        "muxer_opt": {
            "stream_muxers": [
                MPLEXStreamMuxer(),  # Mplex for multiplexing
                YAMUXStreamMuxer(),  # YAMUX as an alternative
            ]
        },
        
        # Enable the relay service
        "relay_opt": {
            "enabled": True,
            "hop": True,  # Allow the node to serve as a relay hop for other peers
            "active": True,  # Actively establish and maintain relay connections
            "discover": True,  # Discover relay nodes
        },
        
        # Enable NAT port mapping
        "nat_opt": {
            "enabled": True,
        },
        
        # Enable the pubsub service with GossipSub
        "pubsub_opt": {
            "enabled": True,
            "router_type": "gossipsub",  # Use GossipSub
            "allow_publish_to_zero_peers": True,  # Allow publishing even if no peers are connected
            "sign_messages": True,  # Sign all messages
            "strict_signing": True,  # Require valid signatures
        },
        
        # User agent for identification
        "user_agent": "universal-connectivity/python-peer",
    }