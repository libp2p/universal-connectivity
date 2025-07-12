#!/usr/bin/env python3
"""
Universal Connectivity Python Peer

This is a Python implementation of the universal connectivity dApp peer,
structured similarly to the go-peer version. It provides a CLI chat application
using libp2p with pubsub and gossipsub for peer-to-peer communication.
"""

import argparse
import logging
import sys
import trio
import trio_asyncio
import socket
import multiaddr

from libp2p import new_host
from libp2p.crypto.rsa import create_new_key_pair
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub
from libp2p.tools.async_service.trio_service import background_trio_service
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.custom_types import TProtocol

from chatroom import ChatRoom, ChatMessage
from ui import NewChatUI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler("py-peer.log", mode='a')  # File output
    ]
)
logger = logging.getLogger("universal-connectivity-py-peer")

# Create a separate logger for system events
system_logger = logging.getLogger("system_events")
system_handler = logging.FileHandler("system_events.txt", mode='a')
system_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
system_logger.addHandler(system_handler)
system_logger.setLevel(logging.INFO)
system_logger.propagate = False  # Don't send to parent loggers

# Constants
DISCOVERY_SERVICE_TAG = "universal-connectivity"
GOSSIPSUB_PROTOCOL_ID = TProtocol("/meshsub/1.0.0")
DEFAULT_PORT = 9095


def find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))  # Bind to a free port provided by the OS
        return s.getsockname()[1]    

async def main_async(args):
    """Main async function with trio-asyncio support."""
    # Enable trio-asyncio mode for running asyncio code in trio context
    async with trio_asyncio.open_loop():
        # Load identity
        key_pair = create_new_key_pair() 
        
        # Determine port
        port = args.port if args.port and args.port != 0 else find_free_port()
        logger.info(f"Using port: {port}")
        
        # Create listen address
        listen_addr = multiaddr.Multiaddr(f"/ip4/0.0.0.0/tcp/{port}")
        
        # Create libp2p host
        host = new_host(
            key_pair=key_pair,
        )
        
        full_multiaddr = f"{listen_addr}/p2p/{host.get_id()}"
        logger.info(f"Host created with PeerID: {host.get_id()}")
        logger.info(f"Listening on: {listen_addr}")
        logger.info(f"Full multiaddr: {full_multiaddr}")
        
        # Log system event
        system_logger.info(f"Peer started - ID: {host.get_id()}, Multiaddr: {full_multiaddr}")
        
        print(f"\n🔗 To connect to this peer, use:")
        print(f'  --connect {full_multiaddr}')
        print(f"\n📋 Multiaddress (copy this):")
        print(f"{full_multiaddr}")
        print()
        
        # Create GossipSub with optimized parameters
        gossipsub = GossipSub(
            protocols=[GOSSIPSUB_PROTOCOL_ID],
            degree=3,  # Number of peers to maintain in mesh
            degree_low=2,  # Lower bound for mesh peers
            degree_high=4,  # Upper bound for mesh peers
        )
        
        # Create PubSub
        pubsub = Pubsub(host, gossipsub)
        
        async with host.run(listen_addrs=[listen_addr]):
            logger.info("Initializing PubSub and GossipSub...")
            
            async with background_trio_service(pubsub):
                async with background_trio_service(gossipsub):
                    logger.info("Pubsub and GossipSub services started.")
                    await pubsub.wait_until_ready()
                    logger.info("Pubsub ready.")
                    
                    # Connect to peer if specified
                    if args.connect:
                        for addr_str in args.connect:
                            try:
                                logger.info(f"Attempting to connect to: {addr_str}")
                                maddr = multiaddr.Multiaddr(addr_str)
                                info = info_from_p2p_addr(maddr)
                                logger.info(f"Connecting to peer: {info.peer_id}")
                                await host.connect(info)
                                logger.info(f"✅ Successfully connected to peer: {info.peer_id}")
                                system_logger.info(f"Connected to peer: {info.peer_id} at {addr_str}")
                                
                                # Wait a bit for the connection to stabilize and gossipsub to sync
                                await trio.sleep(2)
                                
                                # Check if we can see the peer in pubsub
                                connected_peers = list(pubsub.peers.keys())
                                logger.info(f"PubSub peers after connection: {[str(p)[:8] for p in connected_peers]}")
                                
                            except Exception as e:
                                logger.error(f"❌ Failed to connect to {addr_str}: {e}")
                                system_logger.info(f"Failed to connect to {addr_str}: {e}")
                                logger.error(f"Make sure the target peer is running and reachable")
                    
                    # Create and join chat room
                    nickname = args.nick or f"peer-{str(host.get_id())[:8]}"
                    chat_room = await ChatRoom.join_chat_room(
                        host=host,
                        pubsub=pubsub,
                        nickname=nickname,
                        multiaddr=full_multiaddr
                    )
                    
                    logger.info(f"Joined chat room as '{nickname}'")
                    
                    if not args.headless:
                        if args.ui:
                            # Start Textual UI mode
                            logger.info("Starting Textual UI mode...")
                            ui = NewChatUI(chat_room)
                            
                            # Exit trio context to run UI in main thread
                            # This is the cleanest approach for Textual integration
                            return ui  # Return UI instance to run after trio exits
                        else:
                            # Start simple interactive mode (default)
                            logger.info("Starting interactive chat mode...")
                            await chat_room.run_interactive()
                    else:
                        # Run in headless mode
                        logger.info("Running in headless mode. Press Ctrl+C to exit.")
                        try:
                            await trio.sleep_forever()
                        except KeyboardInterrupt:
                            logger.info("Shutting down...")
                    
                    return None  # No UI instance to return


def main():
    """Main entry point."""    
    parser = argparse.ArgumentParser(description="Universal Connectivity Python Peer")
    
    parser.add_argument(
        "--nick",
        type=str,
        help="Nickname to use for the chat"
    )
    
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without chat UI"
    )
    
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Use Textual TUI instead of simple interactive mode"
    )
    
    parser.add_argument(
        "-c", "--connect",
        action="append",
        help="Address to connect to (can be used multiple times)",
        default=[]
    )
    
    parser.add_argument(
        "-p", "--port",
        type=int,
        help="Port to listen on",
        default=0
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Set debug level if verbose flag is provided
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("libp2p").setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    logger.info("Starting Universal Connectivity Python Peer...")
    
    try:
        ui_instance = trio.run(main_async, args)
        
        # If UI instance was returned, run it after trio context
        if ui_instance and args.ui:
            logger.info("Starting Textual UI after trio context...")
            ui_instance.Run()
            
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
