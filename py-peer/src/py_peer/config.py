"""
Configuration module for py-peer.
"""
import argparse
import socket
from dataclasses import dataclass
from typing import Optional

from libp2p.crypto.rsa import create_new_key_pair
from libp2p.crypto.keys import KeyPair
from libp2p.custom_types import TProtocol

# Default values
DEFAULT_TOPIC = "pubsub-chat"
DEFAULT_PORT = 8080
GOSSIPSUB_PROTOCOL_ID = TProtocol("/meshsub/1.0.0")
NOISE_PROTOCOL_ID = TProtocol("/noise")
MPLEX_PROTOCOL_ID = TProtocol("/mplex/6.7.0")


@dataclass
class PeerConfig:
    """Configuration for a libp2p peer."""
    topic: str
    destination: Optional[str]
    port: int
    verbose: bool
    key_pair: KeyPair

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> 'PeerConfig':
        """Create a PeerConfig from command line arguments."""
        # Generate a key pair for the node
        key_pair = create_new_key_pair()
        
        return cls(
            topic=args.topic,
            destination=args.destination,
            port=args.port if args.port != 0 else find_free_port(),
            verbose=args.verbose,
            key_pair=key_pair,
        )


def find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))  # Bind to a free port provided by the OS
        return s.getsockname()[1]


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    description = """
    This program demonstrates a modular pubsub p2p application using libp2p with
    the gossipsub protocol as the pubsub router.
    """

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-t",
        "--topic",
        type=str,
        help="topic name to subscribe",
        default=DEFAULT_TOPIC,
    )

    parser.add_argument(
        "-d",
        "--destination",
        type=str,
        help="Address of peer to connect to",
        default=None,
    )

    parser.add_argument(
        "-p",
        "--port",
        type=int,
        help="Port to listen on",
        default=DEFAULT_PORT,
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    return parser.parse_args()