"""Simple interactive terminal chat interface for the Universal Connectivity peer."""

from __future__ import annotations

import logging
from typing import Any

import trio

from app.errors import ApplicationError
from app.events import EventType
from app.runtime import ApplicationRuntime

logger = logging.getLogger("ui.interactive")


async def run_simple_interactive(runtime: ApplicationRuntime) -> None:
    """Run simple interactive mode."""
    connection_info = runtime.peer.connection_info().to_dict()

    print("\n=== Universal Connectivity Chat ===")
    print(f"Nickname: {connection_info.get('nickname', 'Unknown')}")
    print(f"Peer ID: {connection_info.get('peer_id', 'Unknown')}")
    print(f"Multiaddr: {connection_info.get('multiaddr', 'Unknown')}")
    print("Type messages and press Enter to send. Type 'quit' to exit.")
    print("Commands: /peers, /status, /multiaddr")
    print()

    # Start background task to monitor runtime events
    async with trio.open_nursery() as nursery:
        nursery.start_soon(monitor_runtime_events, runtime)
        nursery.start_soon(handle_user_input, runtime)


async def monitor_runtime_events(runtime: ApplicationRuntime) -> None:
    """Print incoming messages and system events from the runtime EventBus.

    The event bus is the single non-blocking source for every adapter. The
    legacy janus queues remain available to embedders, but the CLI does not
    consume them: consuming both would duplicate every message.
    """
    subscription = runtime.subscribe(
        types={EventType.MESSAGE_RECEIVED, EventType.SYSTEM}
    )
    try:
        while not runtime.stop_event.is_set():
            try:
                while True:
                    event = subscription.get_nowait()
                    if event is None:
                        break
                    _print_runtime_event(event)
            except Exception as e:
                logger.error(f"Error monitoring runtime events: {e}")
            await trio.sleep(0.1)
    finally:
        try:
            runtime.unsubscribe(subscription)
        except Exception:
            logger.debug("Error closing CLI event subscription", exc_info=True)


def _print_runtime_event(event: Any) -> None:
    data = event.data or {}
    if event.type == EventType.MESSAGE_RECEIVED:
        if data.get("type") != "chat_message":
            return
        sender_nick = data.get("sender_nick", "unknown")
        sender_id = data.get("sender_id", "")
        message = data.get("message", "")
        sender_short = sender_id[:8] if len(sender_id) > 8 else sender_id
        print(f"[{sender_nick}({sender_short})]: {message}")
    elif event.type == EventType.SYSTEM:
        if data.get("type") == "system_message":
            print(f"📡 {data.get('message', '')}")


async def handle_user_input(runtime: ApplicationRuntime) -> None:
    """Handle user input in interactive mode."""
    try:
        while True:
            message = await trio.to_thread.run_sync(input)

            if message.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            # Handle special commands
            elif message.strip() == "/peers":
                info = runtime.peer.connection_info().to_dict()
                peers = info.get("connected_peers", [])
                if peers:
                    print(f"📡 Connected peers ({len(peers)}):")
                    for peer in peers:
                        print(f"  - {peer}")
                else:
                    print("📡 No peers connected")
                continue

            elif message.strip() == "/multiaddr":
                info = runtime.peer.connection_info().to_dict()
                print("\n📋 Copy this multiaddress:")
                multiaddrs = info.get("multiaddrs", []) or []
                if multiaddrs:
                    for addr in multiaddrs:
                        print(addr)
                else:
                    print(info.get("multiaddr", "Unknown"))
                print()
                continue

            elif message.strip() == "/status":
                info = runtime.peer.connection_info().to_dict()
                print("📊 Status:")
                print(f"  - Nickname: {info.get('nickname', 'Unknown')}")
                print(f"  - Peer ID: {info.get('peer_id', 'Unknown')}")
                for addr in info.get("multiaddrs", []) or []:
                    print(f"  - Advertised: {addr}")
                for addr in info.get("listen_addrs", []) or []:
                    print(f"  - Listening: {addr}")
                print(f"  - Connected peers: {info.get('peer_count', 0)}")
                topics = sorted(runtime.messaging.subscribed_topics())
                print(f"  - Subscribed topics: {', '.join(topics) or 'none'}")
                continue

            if message.strip():
                # Send message through the application service layer
                try:
                    runtime.messaging.send(message)
                except ApplicationError as e:
                    print(f"❌ {e.message}")

    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")

    runtime.request_stop()
