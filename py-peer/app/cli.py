"""Command-line argument parser and validation for the Universal Connectivity peer."""

from __future__ import annotations

import argparse
from typing import Sequence

from core.constants import DEFAULT_PORT, MAX_BASE_PORT


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


def build_parser() -> argparse.ArgumentParser:
    """Construct the command-line argument parser for py-peer."""
    parser = argparse.ArgumentParser(description="Universal Connectivity Python Peer")

    parser.add_argument(
        "--nick",
        type=str,
        help="Nickname to use for the chat",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without chat UI",
    )

    parser.add_argument(
        "--ui",
        action="store_true",
        help="Use Textual TUI instead of simple interactive mode",
    )

    parser.add_argument(
        "-c",
        "--connect",
        action="append",
        help="Address to connect to (can be used multiple times)",
        default=[],
    )

    parser.add_argument(
        "-p",
        "--port",
        type=_port_type,
        help=(
            f"Port to listen on (default: {DEFAULT_PORT}; 0 picks an ephemeral "
            "port). TCP/QUIC use this port; WebTransport uses port+1 and "
            "WebRTC-direct uses port+2."
        ),
        default=DEFAULT_PORT,
    )

    parser.add_argument(
        "--announce-host",
        type=str,
        default="127.0.0.1",
        dest="announce_host",
        help="Host advertised for wildcard listeners (default: 127.0.0.1; "
        "use your LAN IP so peers on other machines can dial it). "
        "Ignored when --announce-addr is given.",
    )
    parser.add_argument(
        "--listen-addr",
        action="append",
        default=[],
        dest="listen_addrs",
        metavar="MULTIADDR",
        help="Multiaddr to listen on (repeatable). Default: listens on "
        "all supported transports (TCP, WS, QUIC, WebTransport, "
        "WebRTC-direct)",
    )
    parser.add_argument(
        "--announce-addr",
        action="append",
        default=[],
        dest="announce_addrs",
        metavar="MULTIADDR",
        help="Multiaddr to advertise verbatim (repeatable). Overrides "
        "--announce-host. Must be dialable; wildcard hosts are rejected.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--no-strict-signing",
        action="store_true",
        help=(
            "Disable strict message signing. Pubsub then accepts unsigned and "
            "unauthenticated messages: any peer that can reach the topic can "
            "impersonate any sender. Only for interop debugging."
        ),
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
        help="Start Tornado REST + WebSocket API server (headless + API, no UI)",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=8765,
        dest="api_port",
        help="Port for the Tornado API server (default: 8765)",
    )
    parser.add_argument(
        "--api-host",
        type=str,
        default="127.0.0.1",
        dest="api_host",
        help="Interface for the Tornado API server (default: 127.0.0.1). "
        "The API is unauthenticated; use 0.0.0.0 only behind a trusted boundary.",
    )
    parser.add_argument(
        "--api-routes",
        action="store_true",
        help="Print all available API routes and exit",
    )
    parser.add_argument(
        "--max-connections",
        type=int,
        default=500,
        dest="max_connections",
        help="Maximum simultaneous connections (default: 500)",
    )
    parser.add_argument(
        "--min-connections",
        type=int,
        default=50,
        dest="min_connections",
        help="Minimum outbound connections (default: 50)",
    )
    parser.add_argument(
        "--low-watermark",
        type=int,
        default=400,
        dest="low_watermark",
        help="Low watermark for connection pruning (default: 400)",
    )
    parser.add_argument(
        "--high-watermark",
        type=int,
        default=450,
        dest="high_watermark",
        help="High watermark for connection pruning (default: 450)",
    )

    return parser


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments using the default parser."""
    return build_parser().parse_args(args)
