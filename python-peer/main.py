#!/usr/bin/env python3
import asyncio
import logging
import os
import random
import string
import sys
import time
from typing import List, Optional, Dict, Any

import click
from rich.console import Console
from rich.logging import RichHandler

from libp2p import create_libp2p_node
from libp2p_node_config import create_node_config
from chatroom import ChatRoom, ChatMessage
from identity import load_or_create_identity
from ui import ChatUI
from discovery import setup_discovery, discover_peers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("app")

# Constants
DISCOVERY_SERVICE_TAG = "universal-connectivity"
CHAT_TOPIC = "universal-connectivity"
CHAT_FILE_TOPIC = "universal-connectivity-file"
PUBSUB_DISCOVERY_TOPIC = "universal-connectivity-browser-peer-discovery"

def generate_default_nick(peer_id: str) -> str:
    """Generate a default nickname based on username and peer ID."""
    username = os.environ.get("USER", "user")
    short_id = peer_id[-8:] if peer_id else ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{username}-{short_id}"

async def setup_libp2p_node(identity_path: str) -> Any:
    """Initialize and return a libp2p node."""
    private_key = await load_or_create_identity(identity_path)
    config = create_node_config(private_key)
    
    # Create the libp2p node
    node = await create_libp2p_node(config)
    
    logger.info(f"Node started with peer ID: {node.get_id().pretty()}")
    for addr in node.get_addrs():
        logger.info(f"Listening on: {addr}/p2p/{node.get_id().pretty()}")
    
    return node

async def connect_to_peers(node: Any, peers: List[str]) -> None:
    """Connect to a list of peers by multiaddress."""
    for peer_addr in peers:
        try:
            logger.info(f"Connecting to peer: {peer_addr}")
            await node.connect(peer_addr)
            logger.info(f"Successfully connected to {peer_addr}")
        except Exception as e:
            logger.error(f"Failed to connect to {peer_addr}: {e}")

@click.command()
@click.option("--nick", default="", help="Nickname to use in chat (generated if empty)")
@click.option("--identity", default="identity.key", help="Path to identity key file")
@click.option("--headless", is_flag=True, help="Run without chat UI")
@click.option("--connect", multiple=True, help="Multiaddr to connect to (can be used multiple times)")
def main(nick: str, identity: str, headless: bool, connect: List[str]):
    """Universal Connectivity Chat Application - Python Peer"""
    console = Console()
    console.print("[bold blue]Starting Universal Connectivity Python Peer[/bold blue]")
    
    # Start the asyncio event loop
    loop = asyncio.get_event_loop()
    
    try:
        # Setup the libp2p node
        node = loop.run_until_complete(setup_libp2p_node(identity))
        
        # Connect to specified peers
        if connect:
            loop.run_until_complete(connect_to_peers(node, connect))
        
        # Setup peer discovery
        loop.run_until_complete(setup_discovery(node, DISCOVERY_SERVICE_TAG))
        
        # Start DHT-based peer discovery
        discovery_task = loop.create_task(discover_peers(node, DISCOVERY_SERVICE_TAG))
        
        # Use the provided nickname or generate a default one
        nickname = nick if nick else generate_default_nick(node.get_id().pretty())
        
        # Create the chat room
        chat_room = loop.run_until_complete(
            ChatRoom.join(node, CHAT_TOPIC, CHAT_FILE_TOPIC, PUBSUB_DISCOVERY_TOPIC, nickname)
        )
        
        # System message about the node's identity
        chat_room.sys_messages.put_nowait(
            ChatMessage(
                message=f"PeerID: {node.get_id().pretty()}",
                sender_id="system",
                sender_nick="system"
            )
        )
        
        for addr in node.get_addrs():
            chat_room.sys_messages.put_nowait(
                ChatMessage(
                    message=f"Listening on: {addr}/p2p/{node.get_id().pretty()}",
                    sender_id="system",
                    sender_nick="system"
                )
            )
        
        if headless:
            # Run in headless mode without UI
            console.print("[yellow]Running in headless mode. Press Ctrl+C to exit.[/yellow]")
            try:
                loop.run_forever()
            except KeyboardInterrupt:
                pass
        else:
            # Start the UI
            ui = ChatUI(chat_room, node)
            ui_task = loop.create_task(ui.run())
            
            # Run until UI exits
            loop.run_until_complete(ui_task)
    
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        logger.exception("An error occurred")
        return 1
    finally:
        # Clean up
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
        
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        loop.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())