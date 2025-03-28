"""
Main entry point for py-peer.
"""
import trio
import logging

from py_peer.config import parse_args, PeerConfig
from py_peer.peer import Peer
from py_peer.utils.logging import configure_logging


def main() -> None:
    """Main entry point for the application."""
    # Parse command line arguments
    args = parse_args()
    
    # Configure logging
    logger = configure_logging(args.verbose)
    
    # Create peer configuration
    config = PeerConfig.from_args(args)
    
    logger.info("Running py-peer...")
    logger.info(f"Your selected topic is: {config.topic}")
    logger.info(f"Your peer ID is: {config.key_pair.public_key}")
    
    # Create and start the peer
    peer = Peer(config)
    
    try:
        trio.run(peer.start)
    except KeyboardInterrupt:
        logger.info("Application terminated by user")


if __name__ == "__main__":
    main()