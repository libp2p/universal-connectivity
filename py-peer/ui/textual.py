"""
UI module for Universal Connectivity Python Peer

This module provides a Text User Interface (TUI) using Textual for the chat
application. All operations go through the shared ``ApplicationRuntime``
service layer; incoming events arrive on the runtime's ``EventBus``.
"""

import logging
import time
from typing import Any, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Input, Log, Static
from textual.reactive import reactive
from textual.binding import Binding

from app.errors import ApplicationError
from app.events import Event, EventType

logger = logging.getLogger("ui")

# Event types the TUI needs. Filtering in the bus keeps the queue small.
_UI_EVENTS = {
    EventType.MESSAGE_RECEIVED,
    EventType.SYSTEM,
    EventType.PEER_CONNECTED,
    EventType.PEER_DISCONNECTED,
}



class ChatUI(App[None]):
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
        width: 40%;
        min-width: 60;
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

    def __init__(
        self,
        runtime: Any,
        message_queue: Any = None,
        system_queue: Any = None,
    ) -> None:
        super().__init__()
        self.runtime = runtime
        # Kept for queue access; operations go through the service layer.
        self.headless_service = runtime.service
        self.message_queue = message_queue
        self.system_queue = system_queue
        self.running = False

        # One bounded subscription per UI. Headless publishes to this and to
        # the legacy queues, so the TUI must consume exactly one source.
        self._subscription = None
        if hasattr(runtime, "subscribe"):
            self._subscription = runtime.subscribe(types=_UI_EVENTS)
            self.message_queue = None
            self.system_queue = None
        elif message_queue is None or system_queue is None:
            logger.warning(
                "Runtime exposes neither an event bus nor legacy queues; "
                "incoming messages will not be displayed"
            )

        # Get connection info
        self.connection_info = runtime.peer.connection_info().to_dict()

        # Widgets (will be set in compose)
        self.chat_log: Optional[Log] = None
        self.peers_log: Optional[Log] = None
        self.system_log: Optional[Log] = None
        self.message_input: Optional[Input] = None

        logger.info(f"ModularChatUI initialized for peer {self.connection_info.get('peer_id', 'Unknown')}")

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
        for addr in self.connection_info.get("multiaddrs", []) or []:
            self.display_system_message(f"Multiaddr: {addr}")
        self.display_system_message("Commands: /quit, /peers, /status, /multiaddr")

        # Start background tasks
        self.set_interval(1.0, self.refresh_peers)
        self.set_interval(0.1, self._drain_events)

        logger.info("UI mounted and running")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        message = event.value.strip()

        if not message:
            return

        # Clear the input
        if self.message_input is not None:
            self.message_input.clear()

        # Handle commands
        if message.startswith("/"):
            await self._handle_command(message)
            return

        # Send message through the application service layer
        try:
            self.runtime.messaging.send(message)
        except ApplicationError as e:
            logger.warning(f"Message rejected: {e.code}: {e.message}")
            self.display_system_message(f"Error sending message: {e.message}")
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
            info = self.runtime.peer.connection_info().to_dict()
            self.display_system_message(f"Status:")
            self.display_system_message(f"  - Nickname: {info.get('nickname', 'Unknown')}")
            self.display_system_message(f"  - Peer ID: {info.get('peer_id', 'Unknown')}")
            for addr in info.get("multiaddrs", []) or []:
                self.display_system_message(f"  - Advertised: {addr}")
            for addr in info.get("listen_addrs", []) or []:
                self.display_system_message(f"  - Listening: {addr}")
            self.display_system_message(f"  - Connected peers: {info.get('peer_count', 0)}")
            self.display_system_message(f"  - Subscribed topics: chat, discovery")

        elif cmd == "/multiaddr":
            info = self.runtime.peer.connection_info().to_dict()
            self.display_system_message("Copy this multiaddress:")
            multiaddrs = info.get("multiaddrs", []) or []
            if multiaddrs:
                for addr in multiaddrs:
                    self.display_system_message(f"{addr}")
            else:
                self.display_system_message(f"{info.get('multiaddr', 'Unknown')}")

        else:
            self.display_system_message(f"Unknown command: {command}")

    def _drain_events(self) -> None:
        """Deliver queued application events to the UI (non-blocking)."""
        if not self.running:
            return
        subscription = self._subscription
        if subscription is not None:
            try:
                while True:
                    event = subscription.get_nowait()
                    if event is None:
                        break
                    self._handle_event(event)
            except Exception as e:
                logger.error(f"Error draining runtime events: {e}")
            return
        self._drain_legacy_queues()

    def _handle_event(self, event: Event) -> None:
        """Translate one runtime event into UI output."""
        data = event.data or {}
        if event.type == EventType.MESSAGE_RECEIVED:
            if data.get("type") == "chat_message":
                self.display_chat_message(
                    data.get("message", ""),
                    data.get("sender_nick", "unknown"),
                    data.get("sender_id", ""),
                )
            elif data.get("type") == "file_message":
                self.display_system_message(
                    f"{data.get('sender_nick', 'unknown')} shared "
                    f"{data.get('file_name', 'a file')}"
                )
        elif event.type == EventType.SYSTEM:
            if data.get("type") == "system_message":
                self.display_system_message(data.get("message", ""))
        elif event.type in (EventType.PEER_CONNECTED, EventType.PEER_DISCONNECTED):
            peer_id = data.get("peer_id", "unknown")
            state = "connected" if event.type == EventType.PEER_CONNECTED else "disconnected"
            self.display_system_message(f"Peer {state}: {peer_id}")
            self.refresh_peers()

    def _drain_legacy_queues(self) -> None:
        """Fallback for engines without an event bus (kept for embedders)."""
        from queue import Empty

        if self.message_queue is not None:
            try:
                while True:
                    try:
                        message_data = self.message_queue.sync_q.get_nowait()
                    except Empty:
                        break
                    if message_data.get('type') == 'chat_message':
                        self.display_chat_message(
                            message_data.get('message', ''),
                            message_data.get('sender_nick', 'unknown'),
                            message_data.get('sender_id', ''),
                        )
            except Exception as e:
                logger.error(f"Error checking message queue: {e}")

        if self.system_queue is not None:
            try:
                while True:
                    try:
                        system_data = self.system_queue.sync_q.get_nowait()
                    except Empty:
                        break
                    if system_data.get('type') == 'system_message':
                        self.display_system_message(system_data.get('message', ''))
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
        sender_display = sender_nick if not is_self else f"{sender_nick} (You)"

        formatted_message = f"[{timestamp}] {sender_display}: {message}"

        self.chat_log.write_line(formatted_message)

    def display_system_message(self, message: str) -> None:
        """Display a system message."""
        if not self.system_log:
            return

        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        self.system_log.write_line(formatted_message)

    def refresh_peers(self) -> None:
        """Refresh the peers list."""
        peers_log = self.peers_log
        if peers_log is None:
            return

        try:
            info = self.runtime.peer.connection_info().to_dict()
            peers = [str(peer) for peer in info.get('connected_peers', [])]
            peer_count = len(peers)

            # Update reactive peer count
            self.set_reactive(ChatUI.peer_count, peer_count)

            # Clear and update peers list
            peers_log.clear()
            peers_log.write_line(f"Connected: {peer_count}")

            if peers:
                for peer in sorted(peers):
                    peers_log.write_line(f"  • {peer}")
            else:
                peers_log.write_line("  (No peers connected)")

        except Exception as e:
            logger.error(f"Error refreshing peers: {e}")

    async def action_quit(self) -> None:
        """Handle quit action."""
        self.display_system_message("Goodbye!")
        self.running = False
        self.exit()

    def on_unmount(self) -> None:
        """Called when the app is unmounted."""
        self.running = False
        if self._subscription is not None:
            try:
                self.runtime.unsubscribe(self._subscription)
            except Exception:
                logger.debug("Error closing UI event subscription", exc_info=True)
            self._subscription = None
        logger.info("UI unmounted")
