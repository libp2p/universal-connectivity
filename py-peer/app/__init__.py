"""Application service layer for the Universal Connectivity py-peer.

Framework-independent application operations (peers, connections, messaging,
discovery, identity, files, storage) plus a single runtime that owns the one
libp2p host per process.

Adapters (Tornado HTTP/WebSocket, Textual, CLI, future MCP) import from this
package and translate results into their own protocol/UI representation.
Nothing here imports an adapter framework.
"""

from .errors import (
    ApplicationError,
    ConflictError,
    DataDirectoryError,
    NotReadyError,
    NotFoundError,
    OperationError,
    ValidationError,
)
from .models import ConnectionSummary, PeerIdentity, ServiceStatus
from .runtime import ApplicationRuntime, RuntimeConfig

__all__ = [
    "ApplicationError",
    "ConflictError",
    "DataDirectoryError",
    "NotReadyError",
    "NotFoundError",
    "OperationError",
    "ValidationError",
    "ConnectionSummary",
    "PeerIdentity",
    "ServiceStatus",
    "ApplicationRuntime",
    "RuntimeConfig",
]
