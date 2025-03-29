import os
import logging
from typing import Optional

from libp2p.crypto.keys import KeyPair, PrivateKey, PublicKey
from libp2p.crypto.secp256k1 import create_new_key_pair
from libp2p.identity.identify.protocol import IdentifyProtocol

logger = logging.getLogger("app")

async def load_or_create_identity(identity_path: str) -> PrivateKey:
    """
    Load an existing identity key from the given path or create a new one if it doesn't exist.
    
    Args:
        identity_path: Path to the identity key file
        
    Returns:
        PrivateKey: The node's private key
    """
    try:
        # Check if the identity file exists
        if os.path.exists(identity_path):
            logger.info(f"Loading existing identity from {identity_path}")
            with open(identity_path, "rb") as f:
                private_key_bytes = f.read()
                # Deserialize the private key
                private_key = PrivateKey.deserialize(private_key_bytes)
                logger.info(f"Loaded identity with public key: {private_key.get_public_key().serialize().hex()[:16]}...")
                return private_key
        
        # Create a new identity if none exists
        logger.info(f"No existing identity found. Creating new identity at {identity_path}")
        key_pair = create_new_key_pair()
        private_key = key_pair.private_key
        
        # Save the private key to the file
        with open(identity_path, "wb") as f:
            f.write(private_key.serialize())
        
        logger.info(f"Created and saved new identity with public key: {private_key.get_public_key().serialize().hex()[:16]}...")
        return private_key
    
    except Exception as e:
        logger.error(f"Error loading or creating identity: {e}")
        # If there was an error, create an ephemeral key without saving it
        logger.info("Creating ephemeral identity")
        key_pair = create_new_key_pair()
        return key_pair.private_key

async def setup_identify_protocol(node) -> IdentifyProtocol:
    """
    Set up the identify protocol for the node.
    
    Args:
        node: The libp2p node
        
    Returns:
        IdentifyProtocol: The identify protocol instance
    """
    identify_protocol = IdentifyProtocol(node)
    await node.set_stream_handler(identify_protocol.get_protocol_id(), identify_protocol.handler)
    return identify_protocol