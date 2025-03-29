import asyncio
import logging
import os
import time
from typing import Dict, List, Optional, Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.table import Table
from rich.live import Live
from rich.align import Align
from rich import box
import aioconsole

from chatroom import ChatRoom, ChatMessage

logger = logging.getLogger("app")

class ChatUI:
    """
    Text-based UI for the chat application.
    """
    def __init__(self, chat_room: ChatRoom, node):
        """
        Initialize the chat UI.
        
        Args:
            chat_room: The chat room instance
            node: The libp2p node
        """
        self.chat_room = chat_room
        self.node = node
        self.console = Console()
        self.messages: List[Dict[str, Any]] = []
        self.max_messages = 100
        self.command_handlers = {
            "/help": self._handle_help,
            "/peers": self._handle_peers,
            "/nick": self._handle_nick,
            "/connect": self._handle_connect,
            "/file": self._handle_file,
            "/clear": self._handle_clear,
            "/quit": self._handle_quit,
        }
        self.running = False
        self.layout = self._create_layout()
    
    def _create_layout(self) -> Layout:
        """Create the UI layout."""
        layout = Layout()
        
        # Split into top (messages) and bottom (input)
        layout.split(
            Layout(name="main", ratio=9),
            Layout(name="input", ratio=1)
        )
        
        # Split top into messages and info
        layout["main"].split_row(
            Layout(name="messages", ratio=3),
            Layout(name="info", ratio=1)
        )
        
        return layout
    
    def _build_messages_panel(self) -> Panel:
        """Build the panel that displays messages."""
        # Create a text object to hold all messages
        text = Text()
        
        # Add each message to the text
        for msg in self.messages[-self.max_messages:]:
            timestamp = time.strftime("%H:%M:%S", time.localtime(msg.get("timestamp", time.time())))
            
            if msg.get("type") == "system":
                # System messages in yellow
                text.append(f"{timestamp} [System] ", style="yellow")
                text.append(f"{msg['content']}\n", style="yellow")
            else:
                # Chat messages with nickname in appropriate color
                nick = msg.get("nick", "unknown")
                nick_style = "bright_blue" if nick == self.chat_room.nickname else "bright_green"
                
                text.append(f"{timestamp} ", style="dim")
                text.append(f"[{nick}] ", style=nick_style)
                text.append(f"{msg['content']}\n")
        
        # Create and return a panel containing the text
        return Panel(
            text,
            title="Messages",
            border_style="blue",
            box=box.ROUNDED
        )
    
    def _build_info_panel(self) -> Panel:
        """Build the panel that displays peer information."""
        # Create a table for peer information
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Peer ID", style="cyan")
        table.add_column("Status", style="green")
        
        # Add each connected peer to the table
        peers = self.node.get_connected_peers()
        for peer in peers:
            short_id = str(peer)[-12:]
            table.add_row(short_id, "connected")
        
        # Add a help footer
        help_text = Text("\nCommands: /help, /peers, /nick, /connect, /file, /clear, /quit", style="dim")
        
        # Create a layout for info panel content
        info_layout = Layout()
        info_layout.split(
            Layout(Align(table, vertical="top"), name="peers", ratio=4),
            Layout(Align(help_text, vertical="bottom"), name="help", ratio=1)
        )
        
        # Create and return a panel containing the info layout
        return Panel(
            info_layout,
            title=f"Connected Peers ({len(peers)})",
            border_style="green",
            box=box.ROUNDED
        )
    
    def _build_input_panel(self) -> Panel:
        """Build the input panel."""
        text = Text(f"Type a message or command (as {self.chat_room.nickname})...", style="bright_blue")
        return Panel(
            text,
            title="Input",
            border_style="yellow",
            box=box.ROUNDED
        )
    
    def _render_ui(self) -> None:
        """Render the complete UI."""
        # Update the layout with the latest content
        self.layout["messages"].update(self._build_messages_panel())
        self.layout["info"].update(self._build_info_panel())
        self.layout["input"].update(self._build_input_panel())
        
        # Return the layout for rendering
        return self.layout
    
    async def run(self) -> None:
        """Run the chat UI."""
        self.running = True
        
        # Create tasks for handling different message queues
        chat_task = asyncio.create_task(self._handle_chat_messages())
        sys_task = asyncio.create_task(self._handle_sys_messages())
        input_task = asyncio.create_task(self._handle_user_input())
        
        # Clear the screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Add welcome message
        self.messages.append({
            "content": f"Welcome to Universal Connectivity Chat! You are connected as: {self.chat_room.nickname}",
            "timestamp": time.time(),
            "type": "system"
        })
        
        # Start the Live display
        with Live(self._render_ui(), refresh_per_second=4) as live:
            self.live = live
            
            # Wait for any task to complete (or an exception)
            done, pending = await asyncio.wait(
                [chat_task, sys_task, input_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
            
            # Check for exceptions
            for task in done:
                try:
                    await task
                except Exception as e:
                    logger.error(f"Error in UI task: {e}")
            
        self.running = False
    
    async def _handle_chat_messages(self) -> None:
        """Process incoming chat messages."""
        while self.running:
            try:
                # Get the next message
                msg = await self.chat_room.messages.get()
                
                # Add to the message list
                self.messages.append({
                    "content": msg.message,
                    "nick": msg.sender_nick,
                    "sender_id": msg.sender_id,
                    "timestamp": time.time(),
                    "type": "chat"
                })
                
                # Update the UI
                if hasattr(self, "live"):
                    self.live.update(self._render_ui())
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error handling chat message: {e}")
                await asyncio.sleep(1)
    
    async def _handle_sys_messages(self) -> None:
        """Process system messages."""
        while self.running:
            try:
                # Get the next message
                msg = await self.chat_room.sys_messages.get()
                
                # Add to the message list
                self.messages.append({
                    "content": msg.message,
                    "timestamp": time.time(),
                    "type": "system"
                })
                
                # Update the UI
                if hasattr(self, "live"):
                    self.live.update(self._render_ui())
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error handling system message: {e}")
                await asyncio.sleep(1)
    
    async def _handle_user_input(self) -> None:
        """Handle user input."""
        while self.running:
            try:
                # Get user input
                user_input = await aioconsole.ainput("")
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith("/"):
                    command_parts = user_input.split(" ", 1)
                    command = command_parts[0].lower()
                    args = command_parts[1] if len(command_parts) > 1 else ""
                    
                    # Call the appropriate command handler
                    handler = self.command_handlers.get(command)
                    if handler:
                        await handler(args)
                    else:
                        # Unknown command
                        self.messages.append({
                            "content": f"Unknown command: {command}. Type /help for available commands.",
                            "timestamp": time.time(),
                            "type": "system"
                        })
                else:
                    # Regular message - send to chat
                    await self.chat_room.publish(user_input)
                    
                    # Add to local messages
                    self.messages.append({
                        "content": user_input,
                        "nick": self.chat_room.nickname,
                        "sender_id": str(self.node.get_id()),
                        "timestamp": time.time(),
                        "type": "chat"
                    })
                
                # Update the UI
                if hasattr(self, "live"):
                    self.live.update(self._render_ui())
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error handling user input: {e}")
                await asyncio.sleep(1)
    
    async def _handle_help(self, args: str) -> None:
        """Handle the /help command."""
        help_text = """
Available commands:
/help               - Show this help message
/peers              - List connected peers
/nick <name>        - Change your nickname
/connect <multiaddr> - Connect to a peer by multiaddress
/file <path>        - Share a file
/clear              - Clear the message history
/quit               - Exit the application
"""
        self.messages.append({
            "content": help_text,
            "timestamp": time.time(),
            "type": "system"
        })
    
    async def _handle_peers(self, args: str) -> None:
        """Handle the /peers command."""
        peers = self.node.get_connected_peers()
        if not peers:
            self.messages.append({
                "content": "No peers connected.",
                "timestamp": time.time(),
                "type": "system"
            })
            return
        
        peers_text = "Connected peers:\n"
        for i, peer in enumerate(peers, 1):
            peers_text += f"{i}. {peer}\n"
        
        self.messages.append({
            "content": peers_text,
            "timestamp": time.time(),
            "type": "system"
        })
    
    async def _handle_nick(self, args: str) -> None:
        """Handle the /nick command."""
        if not args:
            self.messages.append({
                "content": "Usage: /nick <new_nickname>",
                "timestamp": time.time(),
                "type": "system"
            })
            return
        
        old_nick = self.chat_room.nickname
        self.chat_room.nickname = args
        
        self.messages.append({
            "content": f"Nickname changed from {old_nick} to {args}",
            "timestamp": time.time(),
            "type": "system"
        })
    
    async def _handle_connect(self, args: str) -> None:
        """Handle the /connect command."""
        if not args:
            self.messages.append({
                "content": "Usage: /connect <multiaddress>",
                "timestamp": time.time(),
                "type": "system"
            })
            return
        
        try:
            await self.node.connect(args)
            self.messages.append({
                "content": f"Connected to {args}",
                "timestamp": time.time(),
                "type": "system"
            })
        except Exception as e:
            self.messages.append({
                "content": f"Failed to connect to {args}: {e}",
                "timestamp": time.time(),
                "type": "system"
            })
    
    async def _handle_file(self, args: str) -> None:
        """Handle the /file command."""
        if not args:
            self.messages.append({
                "content": "Usage: /file <file_path>",
                "timestamp": time.time(),
                "type": "system"
            })
            return
        
        try:
            # Read the file
            with open(args, "rb") as f:
                file_data = f.read()
            
            # Share the file
            file_id = await self.chat_room.share_file(file_data, os.path.basename(args))
            
            self.messages.append({
                "content": f"File shared: {args} (ID: {file_id}, {len(file_data)} bytes)",
                "timestamp": time.time(),
                "type": "system"
            })
        except Exception as e:
            self.messages.append({
                "content": f"Failed to share file {args}: {e}",
                "timestamp": time.time(),
                "type": "system"
            })
    
    async def _handle_clear(self, args: str) -> None:
        """Handle the /clear command."""
        self.messages.clear()
        self.messages.append({
            "content": "Message history cleared.",
            "timestamp": time.time(),
            "type": "system"
        })
    
    async def _handle_quit(self, args: str) -> None:
        """Handle the /quit command."""
        self.messages.append({
            "content": "Exiting application...",
            "timestamp": time.time(),
            "type": "system"
        })
        
        if hasattr(self, "live"):
            self.live.update(self._render_ui())
        
        # Wait a moment for the message to be displayed
        await asyncio.sleep(1)
        
        # Stop the UI
        self.running = False
        raise asyncio.CancelledError("User quit")