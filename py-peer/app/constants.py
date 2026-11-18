"""Compatibility re-exports for application constants.

Canonical definitions live in :mod:`core.constants` so the transport engine
does not depend on the application package.
"""

from core.constants import (
    BOOTSTRAP_PEERS,
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_PORT,
    DISCOVERY_SERVICE_TAG,
    FILE_MESSAGE_PREFIX,
    MAX_FILE_QUEUE,
    MAX_GOSSIP_MESSAGE_BYTES,
    MAX_LEGACY_QUEUE,
    MAX_OUTGOING_QUEUE,
    MAX_REQUEST_QUEUE,
    MAX_TOPIC_MESSAGES,
    WEBRTC_DIRECT_PORT_OFFSET,
    WEBTRANSPORT_PORT_OFFSET,
)

__all__ = [
    "BOOTSTRAP_PEERS",
    "DEFAULT_DOWNLOAD_DIR",
    "DEFAULT_PORT",
    "DISCOVERY_SERVICE_TAG",
    "FILE_MESSAGE_PREFIX",
    "MAX_FILE_QUEUE",
    "MAX_GOSSIP_MESSAGE_BYTES",
    "MAX_LEGACY_QUEUE",
    "MAX_OUTGOING_QUEUE",
    "MAX_REQUEST_QUEUE",
    "MAX_TOPIC_MESSAGES",
    "WEBRTC_DIRECT_PORT_OFFSET",
    "WEBTRANSPORT_PORT_OFFSET",
]
