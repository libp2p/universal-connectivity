#!/usr/bin/env python3
"""
Universal Connectivity Python Peer - Modular Main Entry Point

This is the main entry point for the Python implementation of the universal connectivity peer.
It handles argument parsing and coordinates between the headless service and UI components.
"""

import argparse
import logging
import sys
import trio
import asyncio
from typing import Optional

from headless import HeadlessService
from ui_modular import ModularChatUI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler("py-peer.log", mode='a')  # File output
    ]
)
logger = logging.getLogger("main")


async def main_async(args):
    """Main async function."""
    logger.info("Starting Universal Connectivity Python Peer...")
    
    # Create nickname
    nickname = args.nick or f"peer-{trio.current_time():.0f}"
    
    # Create headless service
    headless_service = HeadlessService(
        nickname=nickname,
        port=args.port,
        connect_addrs=args.connect
    )
    
    try:
        if args.headless:
            # Run in headless mode
            logger.info("Starting headless service...")
            await headless_service.start()
        else:
            # Run with UI
            logger.info("Starting headless service in background...")
            
            async with trio.open_nursery() as nursery:
                # Start headless service in background
                nursery.start_soon(headless_service.start)
                
                # Wait for service to be ready
                await headless_service.ready_event.wait()
                logger.info("✅ Headless service is ready, starting UI...")
                
                # Get connection info for UI
                connection_info = headless_service.get_connection_info()
                
                if args.ui:
                    # Exit trio context to run Textual UI
                    return headless_service
                else:
                    # Run simple interactive mode
                    await run_simple_interactive(headless_service)
                    
    except Exception as e:
        logger.error(f"Application error: {e}")
        await headless_service.stop()
        raise
    
    return None


async def run_simple_interactive(headless_service):
    """Run simple interactive mode."""
    connection_info = headless_service.get_connection_info()
    
    print(f"\n=== Universal Connectivity Chat ===")
    print(f"Nickname: {connection_info.get('nickname', 'Unknown')}")
    print(f"Peer ID: {connection_info.get('peer_id', 'Unknown')}")
    print(f"Multiaddr: {connection_info.get('multiaddr', 'Unknown')}")
    print(f"Type messages and press Enter to send. Type 'quit' to exit.")
    print(f"Commands: /peers, /status, /multiaddr")
    print()
    
    try:
        while True:
            message = await trio.to_thread.run_sync(input)
            
            if message.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            
            # Handle special commands
            elif message.strip() == "/peers":
                info = headless_service.get_connection_info()
                peers = info.get('connected_peers', set())
                if peers:
                    print(f"📡 Connected peers ({len(peers)}):")
                    for peer in peers:
                        print(f"  - {peer[:8]}...")
                else:
                    print("📡 No peers connected")
                continue
            
            elif message.strip() == "/multiaddr":
                info = headless_service.get_connection_info()
                print(f"\n📋 Copy this multiaddress:")
                print(f"{info.get('multiaddr', 'Unknown')}")
                print()
                continue
            
            elif message.strip() == "/status":
                info = headless_service.get_connection_info()
                print(f"📊 Status:")
                print(f"  - Multiaddr: {info.get('multiaddr', 'Unknown')}")
                print(f"  - Nickname: {info.get('nickname', 'Unknown')}")
                print(f"  - Connected peers: {info.get('peer_count', 0)}")
                print(f"  - Subscribed topics: chat, discovery")
                continue
            
            if message.strip():
                # Send message through headless service
                await headless_service.send_message(message)
                
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")
    
    await headless_service.stop()


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
        logging.getLogger("headless").setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    try:
        headless_service = trio.run(main_async, args)
        
        # If headless service was returned, run UI after trio context
        if headless_service and args.ui:
            logger.info("Starting Textual UI after trio context...")
            
            # Create and run UI
            ui = ModularChatUI(
                headless_service=headless_service,
                message_queue=headless_service.get_message_queue(),
                system_queue=headless_service.get_system_queue()
            )
            ui.run()
            
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
