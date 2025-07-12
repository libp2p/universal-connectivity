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
import threading
from typing import Optional

from headless import HeadlessService
from ui import ChatUI

# Configure logging
def setup_logging(ui_mode=False):
    """Setup logging configuration based on whether UI is active."""
    handlers = [
        logging.FileHandler("py-peer.log", mode='a')  # Always log to file
    ]
    
    # Only add console handler if not in UI mode
    if not ui_mode:
        handlers.append(logging.StreamHandler())
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True  # Force reconfiguration
    )

logger = logging.getLogger("main")


def run_headless_in_thread(headless_service, ready_event):
    """Run headless service in a separate thread."""
    def run_service():
        try:
            trio.run(headless_service.start)
        except Exception as e:
            logger.error(f"Error in headless service thread: {e}")
    
    # Start the service in a daemon thread
    thread = threading.Thread(target=run_service, daemon=True)
    thread.start()
    
    # Wait for the service to be ready
    import time
    max_wait = 30  # Maximum wait time in seconds
    waited = 0
    while not headless_service.ready and waited < max_wait:
        time.sleep(0.1)
        waited += 0.1
    
    if not headless_service.ready:
        raise RuntimeError("Headless service failed to start within timeout")
    
    logger.info("✅ Headless service is ready in background thread")
    return thread


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
        elif args.ui:
            # Return service configuration for UI mode
            return headless_service
        else:
            # Run with simple interactive mode
            logger.info("Starting headless service in background...")
            
            async with trio.open_nursery() as nursery:
                # Start headless service in background
                nursery.start_soon(headless_service.start)
                
                # Wait for service to be ready
                await headless_service.ready_event.wait()
                logger.info("✅ Headless service is ready, starting UI...")
                
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
    
    # Start background task to monitor message queues
    async with trio.open_nursery() as nursery:
        nursery.start_soon(monitor_message_queues, headless_service)
        nursery.start_soon(handle_user_input, headless_service)


async def monitor_message_queues(headless_service):
    """Monitor message queues and display incoming messages."""
    message_queue = headless_service.get_message_queue()
    system_queue = headless_service.get_system_queue()
    
    if not message_queue or not system_queue:
        logger.warning("Message queues not available")
        return
    
    logger.info("📡 Starting message queue monitoring...")
    
    while True:
        try:
            # Check message queue
            try:
                message_data = message_queue.sync_q.get_nowait()
                logger.info(f"📨 Got message from queue: {message_data}")
                
                if message_data.get('type') == 'chat_message':
                    sender_nick = message_data['sender_nick']
                    sender_id = message_data['sender_id']
                    msg = message_data['message']
                    
                    # Display incoming message
                    sender_short = sender_id[:8] if len(sender_id) > 8 else sender_id
                    print(f"[{sender_nick}({sender_short})]: {msg}")
                    
            except Exception as e:
                logger.debug(f"No message in queue: {e}")
            
            # Check system queue
            try:
                system_data = system_queue.sync_q.get_nowait()
                logger.info(f"📡 Got system message from queue: {system_data}")
                
                if system_data.get('type') == 'system_message':
                    print(f"📡 {system_data['message']}")
                    
            except Exception as e:
                logger.debug(f"No system message in queue: {e}")
            
            await trio.sleep(0.1)  # Small delay to prevent busy waiting
            
        except Exception as e:
            logger.error(f"Error monitoring message queues: {e}")
            await trio.sleep(1)


async def handle_user_input(headless_service):
    """Handle user input in interactive mode."""
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
                headless_service.send_message(message)
                
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
    
    # Default logging setup (will be reconfigured based on mode)
    setup_logging(ui_mode=False)
    
    # Set debug level if verbose flag is provided
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("libp2p").setLevel(logging.DEBUG)
        logging.getLogger("headless").setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    try:
        if args.ui:
            # Configure logging for UI mode (no console output)
            setup_logging(ui_mode=True)
            
            # Special handling for UI mode
            logger.info("Starting in UI mode...")
            
            # Create nickname
            nickname = args.nick or f"peer-{trio.current_time():.0f}"
            
            # Create headless service
            headless_service = HeadlessService(
                nickname=nickname,
                port=args.port,
                connect_addrs=args.connect
            )
            
            # Start headless service in background thread
            logger.info("Starting headless service in background thread...")
            ready_event = threading.Event()
            headless_thread = run_headless_in_thread(headless_service, ready_event)
            
            logger.info("Starting Textual UI in main thread...")
            
            # Create and run UI in main thread
            ui = ChatUI(
                headless_service=headless_service,
                message_queue=headless_service.get_message_queue(),
                system_queue=headless_service.get_system_queue()
            )
            
            # Run UI - this will block until UI exits
            ui.run()
            
        else:
            # Configure logging for non-UI mode (console output enabled)
            setup_logging(ui_mode=False)
            
            # Run the main async function for other modes
            trio.run(main_async, args)
            
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
