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

from app import ApplicationRuntime, RuntimeConfig  # noqa: E402
from app.cli import _port_type, build_parser, parse_args  # noqa: E402, F401
from ui.interactive import run_simple_interactive, _print_runtime_event  # noqa: E402, F401

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




def main() -> None:
    """Main entry point."""
    args = parse_args()

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
