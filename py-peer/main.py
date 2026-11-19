#!/usr/bin/env python3
"""
Universal Connectivity Python Peer - Modular Main Entry Point

This is the main entry point for the Python implementation of the universal connectivity peer.
It handles argument parsing and coordinates between the headless service and UI components.
"""

import argparse
import logging
import signal
import sys
import traceback

import trio
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv
load_dotenv()  # loads .env from cwd (py-peer/)

from core.constants import DEFAULT_PORT, MAX_BASE_PORT  # noqa: E402
from app import ApplicationError, ApplicationRuntime, RuntimeConfig  # noqa: E402

def _port_type(value: str) -> int:
    """Parse ``--port`` and reject values the transport offsets cannot serve.

    The default listener set uses ``port``, ``port + 1`` (WebTransport) and
    ``port + 2`` (WebRTC-direct), so the base must leave room for both offsets.
    Validating here turns a late ``Invalid listen address`` error during host
    startup into an immediate, actionable CLI error.
    """
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid port: {value!r}") from exc
    if not 0 <= port <= MAX_BASE_PORT:
        raise argparse.ArgumentTypeError(
            f"port must be between 0 and {MAX_BASE_PORT} (0 = ephemeral); "
            "port+1 and port+2 are used by WebTransport and WebRTC-direct"
        )
    return port

def build_runtime(args: argparse.Namespace) -> ApplicationRuntime:
    """Create the single runtime that owns the peer for this process."""
    runtime = ApplicationRuntime(RuntimeConfig.from_namespace(args))
    paths = getattr(runtime, "paths", None)
    if paths is not None:
        logger.info(
            f"Data directory: {paths.root} (from {paths.source}); "
            f"identity: {paths.identity_file}"
        )
    return runtime

# Configure logging
def setup_logging(ui_mode: bool = False) -> None:
    """Setup logging configuration based on whether UI is active."""
    handlers: list[logging.Handler] = []

    # Only add console handler if not in UI mode
    if not ui_mode:
        handlers.append(logging.StreamHandler())

    # If no handlers, add a null handler to prevent logging errors
    if not handlers:
        handlers.append(logging.NullHandler())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(message)s",
        handlers=handlers,
        force=True  # Force reconfiguration
    )

logger = logging.getLogger("main")


def install_shutdown_signal_handlers(
    headless_service: Any,
    on_signal: Callable[[], Any] | None = None,
) -> dict[int, Any]:
    """Map SIGINT/SIGTERM to a graceful stop request.

    Must run on the main thread. Returns the handlers that were replaced so
    the caller can restore them. ``on_signal`` runs after ``request_stop()``
    and is used by API mode to wake the Tornado IOLoop immediately.
    """
    previous: dict[int, Any] = {}

    def _handler(signum: int, frame: Any) -> None:
        logger.info(
            f"Received signal {signum}; requesting graceful shutdown..."
        )
        headless_service.request_stop()
        if on_signal is not None:
            try:
                on_signal()
            except Exception:
                logger.exception("Error in shutdown signal callback")

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[sig] = signal.signal(sig, _handler)
        except (ValueError, OSError):
            # Not on the main thread, or the signal is unsupported here.
            pass
    return previous


def restore_signal_handlers(previous: dict[int, Any]) -> None:
    for sig, handler in previous.items():
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass


async def main_async(args: argparse.Namespace) -> ApplicationRuntime | None:
    """Main async function."""
    logger.info("Starting Universal Connectivity Python Peer...")

    runtime = build_runtime(args)

    try:
        if args.headless:
            # Run in headless mode. There is no UI to handle Ctrl-C, so map
            # SIGINT/SIGTERM to a stop request and let start()'s finally
            # block perform the graceful teardown.
            logger.info("Starting application runtime...")
            previous_handlers = install_shutdown_signal_handlers(runtime)
            try:
                await runtime.start()
            finally:
                restore_signal_handlers(previous_handlers)
        elif args.ui:
            # Return the runtime for the UI mode handler in main().
            return runtime
        else:
            # Run with simple interactive mode
            logger.info("Starting application runtime in background...")

            async with trio.open_nursery() as nursery:
                nursery.start_soon(runtime.start)

                await runtime.service.ready_event.wait()
                logger.info("✅ Runtime is ready, starting interactive mode...")

                await run_simple_interactive(runtime)

    except Exception as e:
        logger.error(f"Application error: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        runtime.request_stop()
        raise

    return None


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
    from app.events import EventType

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
    from app.events import EventType

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
                peers = info.get('connected_peers', [])
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
                    print(info.get('multiaddr', 'Unknown'))
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


def main() -> None:
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
        type=_port_type,
        help=(
            f"Port to listen on (default: {DEFAULT_PORT}; 0 picks an ephemeral "
            "port). TCP/QUIC use this port; WebTransport uses port+1 and "
            "WebRTC-direct uses port+2."
        ),
        default=DEFAULT_PORT
    )

    parser.add_argument(
        "--announce-host",
        type=str,
        default="127.0.0.1",
        dest="announce_host",
        help="Host advertised for wildcard listeners (default: 127.0.0.1; "
             "use your LAN IP so peers on other machines can dial it). "
             "Ignored when --announce-addr is given."
    )
    parser.add_argument(
        "--listen-addr",
        action="append",
        default=[],
        dest="listen_addrs",
        metavar="MULTIADDR",
        help="Multiaddr to listen on (repeatable). Default: listens on "
             "all supported transports (TCP, WS, QUIC, WebTransport, "
             "WebRTC-direct)"
    )
    parser.add_argument(
        "--announce-addr",
        action="append",
        default=[],
        dest="announce_addrs",
        metavar="MULTIADDR",
        help="Multiaddr to advertise verbatim (repeatable). Overrides "
             "--announce-host. Must be dialable; wildcard hosts are rejected."
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging"
    )

    parser.add_argument(
        "--no-strict-signing",
        action="store_true",
        help=(
            "Disable strict message signing. Pubsub then accepts unsigned and "
            "unauthenticated messages: any peer that can reach the topic can "
            "impersonate any sender. Only for interop debugging."
        )
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=str,
        default=None,
        help="Deterministic peer ID for development/testing, derived from this "
             "seed and not written to disk. Default: a persisted random "
             "identity in the data directory.",
    )
    parser.add_argument(
        "-t",
        "--topic",
        type=str,
        help="Custom topic to subscribe.",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        dest="data_dir",
        metavar="PATH",
        help="Directory for the peer identity, message history, and system log "
             "(default: $UC_DATA_DIR, else the platform data directory).",
    )
    parser.add_argument(
        "--storage-path",
        type=str,
        default=None,
        dest="storage_path",
        metavar="PATH",
        help="SQLite file for message history (default: <data-dir>/history.db). "
             "Use :memory: for an ephemeral SQLite database.",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Start Tornado REST + WebSocket API server (headless + API, no UI)"
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=8765,
        dest="api_port",
        help="Port for the Tornado API server (default: 8765)"
    )
    parser.add_argument(
        "--api-host",
        type=str,
        default="127.0.0.1",
        dest="api_host",
        help="Interface for the Tornado API server (default: 127.0.0.1). "
             "The API is unauthenticated; use 0.0.0.0 only behind a trusted boundary."
    )
    parser.add_argument(
        "--api-routes",
        action="store_true",
        help="Print all available API routes and exit"
    )
    parser.add_argument(
        "--max-connections",
        type=int,
        default=500,
        dest="max_connections",
        help="Maximum simultaneous connections (default: 500)"
    )
    parser.add_argument(
        "--min-connections",
        type=int,
        default=50,
        dest="min_connections",
        help="Minimum outbound connections (default: 50)"
    )
    parser.add_argument(
        "--low-watermark",
        type=int,
        default=400,
        dest="low_watermark",
        help="Low watermark for connection pruning (default: 400)"
    )
    parser.add_argument(
        "--high-watermark",
        type=int,
        default=450,
        dest="high_watermark",
        help="High watermark for connection pruning (default: 450)"
    )

    args = parser.parse_args()

    # Default logging setup (will be reconfigured based on mode)
    setup_logging(ui_mode=False)

    # Set debug level if verbose flag is provided
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for _name in (
            "headless",
            "chatroom",
            "libp2p",
            "libp2p.transport",
            "libp2p.security",
            "libp2p.mux",
            "libp2p.stream",
            "libp2p.pubsub",
            "libp2p.discovery",
            "libp2p.kad_dht",
        ):
            logging.getLogger(_name).setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Print routes and exit early if requested
    if getattr(args, 'api_routes', False):
        from api.server import _print_routes
        _print_routes(getattr(args, 'api_port', 8765))
        sys.exit(0)

    try:
        if args.api:
            # ── Tornado API mode ─────────────────────────────────────────────
            setup_logging(ui_mode=False)
            logger.info("Starting in API mode (HeadlessService + Tornado REST server)...")

            runtime = build_runtime(args)

            # One runtime owns the single peer host for this process.
            logger.info("Starting application runtime in background thread...")
            runtime.start_in_thread()
            logger.info(f"✅ HeadlessService ready — launching Tornado on {args.api_host}:{args.api_port}")

            # Start Tornado in the main thread (blocks here)
            from api.server import TornadoServer, _print_routes
            _print_routes(args.api_port)
            server = TornadoServer(runtime, port=args.api_port, host=args.api_host)
            previous_handlers = install_shutdown_signal_handlers(
                runtime, on_signal=server.stop
            )
            try:
                server.start()  # blocks until Ctrl-C or the headless service stops
            finally:
                restore_signal_handlers(previous_handlers)
                # Covers /service/stop, Ctrl-C, SIGTERM, and adapter failures
                # (for example a bind conflict) so the peer listener never
                # outlives the API process.
                runtime.request_stop()
                runtime.join(10.0)
                runtime.close()

            # A clean /service/stop exits 0; a crashed headless thread exits 1
            # so systemd (Restart=on-failure) can bring the node back.
            if runtime.failed:
                logger.error("Headless service failed; exiting with status 1.")
                sys.exit(1)

        elif args.ui:
            # Configure logging for UI mode (no console output)
            setup_logging(ui_mode=True)

            # Imported lazily: headless, CLI, and API modes must not require a
            # TUI framework to be importable.
            from ui.textual import ChatUI

            # Special handling for UI mode
            logger.info("Starting in UI mode...")

            runtime = build_runtime(args)

            # Start the shared runtime in a background thread
            logger.info("Starting application runtime in background thread...")
            runtime.start_in_thread()

            logger.info("Starting Textual UI in main thread...")

            try:
                # Create and run UI in main thread. The UI subscribes to the
                # runtime EventBus; no legacy queues are needed.
                ui = ChatUI(runtime=runtime)

                # Run UI - this will block until UI exits
                ui.run()
            finally:
                # Tear the peer down instead of letting the daemon thread die
                # with the process.
                runtime.request_stop()
                runtime.join(10.0)
                runtime.close()

        else:
            # Configure logging for non-UI mode (console output enabled)
            setup_logging(ui_mode=False)

            # Run the main async function for other modes
            trio.run(main_async, args)

    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
