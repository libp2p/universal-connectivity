"""
UI module for Universal Connectivity Python Peer

This module provides a Text User Interface (TUI) using Textual for the chat application.
It mirrors the functionality and layout of the go-peer UI implementation.
"""

import logging
import time
from typing import Optional, List
import trio
import asyncio
from trio import MemoryReceiveChannel, MemorySendChannel

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Input, Log, Static, TextArea
from textual.reactive import reactive
from textual.message import Message
from textual import events
from textual.binding import Binding

from chatroom import ChatRoom, ChatMessage

logger = logging.getLogger("ui")


class ChatUI(App[None]):
    """
    A Textual-based Text User Interface (TUI) for the ChatRoom.
    
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
        width: 25%;
        height: 1fr;
        margin: 1;
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
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]
    
    # Reactive attributes
    peer_count = reactive(0)
    
    def __init__(self, chat_room: ChatRoom):
        super().__init__()
        self.chat_room = chat_room
        self.running = False
        
        # Use simple queues for thread-safe communication
        import queue
        self.message_queue = queue.Queue()
        self.ui_to_chat_queue = queue.Queue()
        
        # Widgets (will be set in compose)
        self.chat_log: Optional[Log] = None
        self.peers_log: Optional[Log] = None
        self.system_log: Optional[Log] = None
        self.message_input: Optional[Input] = None
        
        logger.info(f"ChatUI initialized for peer {self.chat_room.peer_id[:8]}...")
    
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
            yield Input(
                placeholder=f"{self.chat_room.nickname} > Type your message...",
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
        self.chat_log.border_title = f"Room: {getattr(self.chat_room, 'room_name', 'universal-connectivity')}"
        self.peers_log.border_title = "Peers"
        self.system_log.border_title = "System"
        
        # Focus the input field
        self.message_input.focus()
        
        # Start the chat handlers
        self.running = True
        
        # Display welcome message
        self.display_system_message("Universal Connectivity Chat Started")
        self.display_system_message(f"Nickname: {self.chat_room.nickname}")
        self.display_system_message(f"Multiaddr: {self.chat_room.multiaddr}")
        self.display_system_message("Commands: /quit, /peers, /status, /multiaddr")
        
        # Start background tasks
        self.set_interval(1.0, self.refresh_peers)
        self.set_interval(0.1, self._check_message_queue)
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        message = event.value.strip()
        
        if not message:
            return
            
        # Clear the input
        self.message_input.clear()
        
        # Handle special commands
        if message == "/quit":
            await self.action_quit()
            return
        elif message == "/peers":
            await self._show_peers()
            return
        elif message == "/status":
            await self._show_status()
            return
        elif message == "/multiaddr":
            await self._show_multiaddr()
            return
        
        # Send regular message - put in queue for background thread to handle
        try:
            self.ui_to_chat_queue.put(("message", message))
            # Display in our own chat log immediately
            self.display_self_message(message)
        except Exception as e:
            self.display_system_message(f"Error queuing message: {e}")
    
    def _check_message_queue(self) -> None:
        """Check for incoming messages from the chat room."""
        import queue
        try:
            while True:
                try:
                    msg_type, data = self.message_queue.get_nowait()
                    if msg_type == "chat_message":
                        self.display_chat_message(data)
                    elif msg_type == "system_message":
                        self.display_system_message(data)
                    elif msg_type == "peers_update":
                        # Peers will be refreshed by the interval timer
                        pass
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"Error checking message queue: {e}")
    
    def refresh_peers(self) -> None:
        """Update the peers list display."""
        if not self.peers_log:
            return
            
        try:
            peers = self.chat_room.get_connected_peers()
            self.peer_count = len(peers)
            
            # Clear and update peers list
            self.peers_log.clear()
            
            if peers:
                for peer_id in sorted(peers):
                    short_id = self._short_id(peer_id)
                    self.peers_log.write_line(f"[bold]{short_id}[/bold]")
            else:
                self.peers_log.write_line("[dim]No peers connected[/dim]")
                
        except Exception as e:
            logger.error(f"Error refreshing peers: {e}")
    
    def display_chat_message(self, chat_msg: ChatMessage) -> None:
        """Display a chat message from another peer."""
        if not self.chat_log:
            return
            
        try:
            sender_short = self._short_id(chat_msg.sender_id)
            timestamp = time.strftime("%H:%M:%S", time.localtime(chat_msg.timestamp))
            
            # Format: [timestamp] <nick(short_id)>: message
            formatted_msg = (
                f"[dim]{timestamp}[/dim] "
                f"[bold green]<{chat_msg.sender_nick}({sender_short})>[/bold green]: "
                f"{chat_msg.message}"
            )
            
            self.chat_log.write_line(formatted_msg)
            
        except Exception as e:
            logger.error(f"Error displaying chat message: {e}")
    
    def display_self_message(self, message: str) -> None:
        """Display a message sent by the local user."""
        if not self.chat_log:
            return
            
        try:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            sender_short = self._short_id(self.chat_room.peer_id)
            
            # Format: [timestamp] <nick(short_id)>: message  
            formatted_msg = (
                f"[dim]{timestamp}[/dim] "
                f"[bold yellow]<{self.chat_room.nickname}({sender_short})>[/bold yellow]: "
                f"{message}"
            )
            
            self.chat_log.write_line(formatted_msg)
            
        except Exception as e:
            logger.error(f"Error displaying self message: {e}")
    
    def display_system_message(self, message: str) -> None:
        """Display a system message."""
        if not self.system_log:
            return
            
        try:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            formatted_msg = f"[dim]{timestamp}[/dim] [bold blue]System[/bold blue]: {message}"
            
            self.system_log.write_line(formatted_msg)
            
        except Exception as e:
            logger.error(f"Error displaying system message: {e}")
    
    async def _show_peers(self) -> None:
        """Show connected peers information."""
        peers = self.chat_room.get_connected_peers()
        if peers:
            self.display_system_message(f"Connected peers ({len(peers)}):")
            for peer_id in sorted(peers):
                self.display_system_message(f"  - {peer_id}")
        else:
            self.display_system_message("No peers connected")
    
    async def _show_multiaddr(self) -> None:
        """Show multiaddress for easy copying."""
        self.display_system_message("📋 Copy this multiaddress:")
        self.display_system_message(f"{self.chat_room.multiaddr}")
    
    async def _show_status(self) -> None:
        """Show status information."""
        peer_count = self.chat_room.get_peer_count()
        self.display_system_message("Status:")
        self.display_system_message(f"  - Multiaddr: {self.chat_room.multiaddr}")
        self.display_system_message(f"  - Nickname: {self.chat_room.nickname}")
        self.display_system_message(f"  - Connected peers: {peer_count}")
        self.display_system_message(f"  - Subscribed topics: chat, discovery")
    
    def _short_id(self, peer_id: str) -> str:
        """Return a short version of the peer ID (last 8 characters)."""
        if len(peer_id) > 8:
            return peer_id[-8:]
        return peer_id
    
    async def action_quit(self) -> None:
        """Quit the application."""
        self.running = False
        self.ui_to_chat_queue.put(("quit", None))
        self.exit()
    
    def Run(self) -> None:
        """Run the UI - matches go-peer ui.Run() method."""
        # Add message handler to chat room
        async def message_handler(chat_msg: ChatMessage):
            if self.message_queue:
                self.message_queue.put(("chat_message", chat_msg))
        
        self.chat_room.add_message_handler(message_handler)
        
        # Start background threads for networking
        import threading
        
        def run_chat_handlers():
            """Run chat room message handlers in background thread."""
            try:
                logger.info("Starting background chat handlers...")
                trio.run(self.chat_room.start_message_handlers)
            except Exception as e:
                logger.error(f"Error in background chat handlers: {e}")
        
        def run_message_publisher():
            """Handle messages from UI to chat room."""
            import queue
            while self.running:
                try:
                    try:
                        msg_type, data = self.ui_to_chat_queue.get_nowait()
                        if msg_type == "message":
                            # Publish message in background
                            def publish_message():
                                try:
                                    trio.run(self.chat_room.publish_message, data)
                                    logger.debug(f"Published message: {data}")
                                except Exception as e:
                                    logger.error(f"Error publishing message: {e}")
                            
                            pub_thread = threading.Thread(target=publish_message, daemon=True)
                            pub_thread.start()
                            
                        elif msg_type == "quit":
                            logger.info("UI requested quit")
                            break
                    except queue.Empty:
                        pass
                    
                    import time
                    time.sleep(0.1)  # Small delay to prevent busy loop
                    
                except Exception as e:
                    logger.error(f"Error in message publisher: {e}")
                    import time
                    time.sleep(1.0)
        
        # Start background threads
        chat_thread = threading.Thread(target=run_chat_handlers, daemon=True)
        pub_thread = threading.Thread(target=run_message_publisher, daemon=True)
        
        chat_thread.start()
        pub_thread.start()
        
        # Give background threads time to start
        import time
        time.sleep(0.5)
        
        # Run UI in main thread
        logger.info("🚀 Starting UI in main thread...")
        try:
            super().run()
        except KeyboardInterrupt:
            logger.info("UI interrupted by user")
        except Exception as e:
            logger.error(f"Error running UI: {e}")
        finally:
            self.running = False


def NewChatUI(chat_room: ChatRoom) -> ChatUI:
    """Create a new ChatUI instance - matches go-peer NewChatUI function."""
    return ChatUI(chat_room)
