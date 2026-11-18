"""Transport and application constants.

These definitions live in ``core`` so the transport engine does not import the
application package. ``app.constants`` re-exports them for service-layer code.
"""

from __future__ import annotations

import os

# Bootstrap nodes for peer discovery.
BOOTSTRAP_PEERS = [
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zp7ykQCj2gRNdrFeqQ1vG13rMb4sPS",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt",
    "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb",
]

# Prefix used to mark a chat message as a file-share announcement.
FILE_MESSAGE_PREFIX = "[FILE]"

# Default download directory for shared/downloaded files.
DEFAULT_DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

# Resource bounds. The API and the network are untrusted inputs: without caps
# a slow client, a busy topic, or a message flood can grow these structures
# until the peer is OOM-killed.
MAX_TOPIC_MESSAGES = 1000        # stored history per topic
MAX_LEGACY_QUEUE = 1024          # UI compatibility queue
MAX_OUTGOING_QUEUE = 1024        # API/UI -> chat publisher
MAX_REQUEST_QUEUE = 256          # topic/peer requests
MAX_FILE_QUEUE = 64              # file share/download requests

# Largest inbound gossip payload accepted from a remote peer. Anything bigger
# is dropped before decoding, so a peer cannot force unbounded JSON/protobuf
# parsing or storage growth.
MAX_GOSSIP_MESSAGE_BYTES = 64 * 1024

# Discovery service tag and default listener port.
DISCOVERY_SERVICE_TAG = "universal-connectivity"
DEFAULT_PORT = 4001

# The default listener set binds one port per transport family. WebTransport
# and WebRTC-direct cannot share the QUIC-v1 socket (each owns its own
# certificate), so they are offset from the base port. When the base port is
# 0 (ephemeral) every transport binds its own kernel-assigned port instead.
WEBTRANSPORT_PORT_OFFSET = 1
WEBRTC_DIRECT_PORT_OFFSET = 2

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
