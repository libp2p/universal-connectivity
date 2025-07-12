"""
UI module for Universal Connectivity Python Peer - Modular Version

This module provides a Text User Interface (TUI) using Textual for the chat application.
It works with the headless service and uses queues for communication.
"""

import logging
import time
import threading
from typing import Optional, Any, Dict
from queue import Queue, Empty

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Input, Log, Static
from textual.reactive import reactive
from textual.binding import Binding

logger = logging.getLogger("ui_modular")


class ModularChatUI(App[None]):
    """
    A Textual-based Text User Interface (TUI) that works with the headless service.
    
    The UI provides:
    - A main chat message area (left side)
    - A peers list panel (right side)  
    - A system messages area (bottom)
    - An input field for typing messages
    """
    
    CSS = """
    #chat-container {
        height: 3fr;
    }
    
    #chat-messages {
        border: solid $primary;
        border-title-align: left;
        height: 1fr;
        margin: 1;
    }
    
    #peers-list {
        border: solid $primary;
        border-title-align: left;
        height: 1fr;
        margin: 1;
        width: 30%;
    }
    
    #system-messages {
        border: solid $primary;
        border-title-align: left;
        height: 2fr;
        margin: 1;
    }
    
    #input-container {
        height: 3;
        margin: 1;
    }
    
    #message-input {
        border: solid $primary;
    }
    
    .peer-id {
        color: $text-muted;
    }
    
    .sender-self {
        color: $warning;
    }
    
    .sender-other {
        color: $success;
    }
    
    .system-message {
        color: $accent;
    }
    
    Log {
        scrollbar-size: 0 0;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]
    
    # Reactive attributes
    peer_count = reactive(0)
    
    def __init__(self, headless_service, message_queue, system_queue):
        super().__init__()
        self.headless_service = headless_service
        self.message_queue = message_queue
        self.system_queue = system_queue
        self.running = False
        
        # Get connection info
        self.connection_info = self.headless_service.get_connection_info()
        
        # Widgets (will be set in compose)
        self.chat_log: Optional[Log] = None
        self.peers_log: Optional[Log] = None
        self.system_log: Optional[Log] = None
        self.message_input: Optional[Input] = None
        
        logger.info(f"ModularChatUI initialized for peer {self.connection_info.get('peer_id', 'Unknown')[:8]}...")
    
    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        
        with Container(id="chat-container"):
            with Horizontal():
                # Main chat messages area
                yield Log(
                    id="chat-messages",
                    name="chat-messages",
                    highlight=True,
                    auto_scroll=True,
                    max_lines=1000,
                ).add_class("chat-messages")
                
                # Peers list
                yield Log(
                    id="peers-list", 
                    name="peers-list",
                    highlight=True,
                    auto_scroll=False,
                    max_lines=100,
                ).add_class("peers-list")
        
        # System messages area
        yield Log(
            id="system-messages",
            name="system-messages", 
            highlight=True,
            auto_scroll=True,
            max_lines=200,
        ).add_class("system-messages")
        
        # Input field
        with Container(id="input-container"):
            nickname = self.connection_info.get('nickname', 'Unknown')
            yield Input(
                placeholder=f"{nickname} > Type your message...",
                id="message-input",
                name="message-input",
            )
    
    def on_mount(self) -> None:
        """Called when the app is mounted."""
        # Get widget references
        self.chat_log = self.query_one("#chat-messages", Log)
        self.peers_log = self.query_one("#peers-list", Log) 
        self.system_log = self.query_one("#system-messages", Log)
        self.message_input = self.query_one("#message-input", Input)
        
        # Set titles
        self.chat_log.border_title = "Room: universal-connectivity"
        self.peers_log.border_title = "Peers"
        self.system_log.border_title = "System"
        
        # Focus the input field
        self.message_input.focus()
        
        # Start the UI
        self.running = True
        
        # Display welcome message
        self.display_system_message("Universal Connectivity Chat Started")
        self.display_system_message(f"Nickname: {self.connection_info.get('nickname', 'Unknown')}")
        self.display_system_message(f"Multiaddr: {self.connection_info.get('multiaddr', 'Unknown')}")
        self.display_system_message("Commands: /quit, /peers, /status, /multiaddr")
        
        # Start background tasks
        self.set_interval(1.0, self.refresh_peers)
        self.set_interval(0.1, self._check_queues)
        
        logger.info("UI mounted and running")
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        message = event.value.strip()
        
        if not message:
            return
            
        # Clear the input
        self.message_input.clear()
        
        # Handle commands
        if message.startswith("/"):
            await self._handle_command(message)
            return
        
        # Send message through headless service
        try:
            self.headless_service.send_message(message)  # Now synchronous
            
            # Display own message
            nickname = self.connection_info.get('nickname', 'Unknown')
            self.display_chat_message(message, nickname, "self")
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self.display_system_message(f"Error sending message: {e}")
    
    async def _handle_command(self, command: str) -> None:
        """Handle special commands."""
        cmd = command.lower().strip()
        
        if cmd in ["/quit", "/exit", "/q"]:
            self.display_system_message("Goodbye!")
            self.exit()
        
        elif cmd == "/peers":
            self.refresh_peers()
        
        elif cmd == "/status":
            info = self.headless_service.get_connection_info()
            self.display_system_message(f"Status:")
            self.display_system_message(f"  - Multiaddr: {info.get('multiaddr', 'Unknown')}")
            self.display_system_message(f"  - Nickname: {info.get('nickname', 'Unknown')}")
            self.display_system_message(f"  - Connected peers: {info.get('peer_count', 0)}")
            self.display_system_message(f"  - Subscribed topics: chat, discovery")
        
        elif cmd == "/multiaddr":
            info = self.headless_service.get_connection_info()
            self.display_system_message("Copy this multiaddress:")
            self.display_system_message(f"{info.get('multiaddr', 'Unknown')}")
        
        else:
            self.display_system_message(f"Unknown command: {command}")
    
    def _check_queues(self) -> None:
        """Check queues for new messages."""
        if not self.running:
            return
            
        # Check message queue
        try:
            while True:
                try:
                    message_data = self.message_queue.sync_q.get_nowait()
                    if message_data.get('type') == 'chat_message':
                        self.display_chat_message(
                            message_data['message'],
                            message_data['sender_nick'],
                            message_data['sender_id']
                        )
                except Empty:
                    break
        except Exception as e:
            logger.error(f"Error checking message queue: {e}")
        
        # Check system queue
        try:
            while True:
                try:
                    system_data = self.system_queue.sync_q.get_nowait()
                    if system_data.get('type') == 'system_message':
                        self.display_system_message(system_data['message'])
                except Empty:
                    break
        except Exception as e:
            logger.error(f"Error checking system queue: {e}")
    
    def display_chat_message(self, message: str, sender_nick: str, sender_id: str) -> None:
        """Display a chat message."""
        if not self.chat_log:
            return
        
        # Determine if it's our own message
        our_peer_id = self.connection_info.get('peer_id', '')
        is_self = sender_id == our_peer_id or sender_id == "self"
        
        # Format message
        timestamp = time.strftime("%H:%M:%S")
        sender_class = "sender-self" if is_self else "sender-other"
        sender_display = sender_nick if not is_self else f"{sender_nick} (You)"
        
        formatted_message = f"[{timestamp}] [{sender_class}]{sender_display}[/{sender_class}]: {message}"
        
        self.chat_log.write_line(formatted_message)
    
    def display_system_message(self, message: str) -> None:
        """Display a system message."""
        if not self.system_log:
            return
        
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] [system-message]{message}[/system-message]"
        
        self.system_log.write_line(formatted_message)
    
    def refresh_peers(self) -> None:
        """Refresh the peers list."""
        if not self.peers_log:
            return
        
        try:
            info = self.headless_service.get_connection_info()
            peers = info.get('connected_peers', set())
            peer_count = len(peers)
            
            # Update reactive peer count
            self.peer_count = peer_count
            
            # Clear and update peers list
            self.peers_log.clear()
            self.peers_log.write_line(f"Connected: {peer_count}")
            
            if peers:
                for peer in sorted(peers):
                    peer_short = peer[:8] if len(peer) > 8 else peer
                    self.peers_log.write_line(f"  • {peer_short}...")
            else:
                self.peers_log.write_line("  (No peers connected)")
                
        except Exception as e:
            logger.error(f"Error refreshing peers: {e}")
    
    def action_quit(self) -> None:
        """Handle quit action."""
        self.display_system_message("Goodbye!")
        self.running = False
        self.exit()
    
    def on_unmount(self) -> None:
        """Called when the app is unmounted."""
        self.running = False
        logger.info("UI unmounted")


# Alias for backwards compatibility
NewChatUI = ModularChatUI
