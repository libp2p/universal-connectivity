"""Application-level exceptions.

Services raise these instead of framework-specific errors. Adapters map them to
HTTP status codes, UI messages, or MCP error objects.

Rules:
- No service imports an HTTP/UI framework.
- Messages are safe to return to a local client (no secrets, no key bytes).
- ``detail`` carries optional machine-readable context.
"""

from typing import Any


class ApplicationError(Exception):
    """Base class for application-level failures."""

    code = "application_error"
    http_status = 500

    def __init__(self, message: str, *, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        payload = {"code": self.code, "message": self.message}
        if self.detail:
            payload["detail"] = self.detail
        return payload


class ValidationError(ApplicationError):
    """Caller supplied input that violates a domain rule."""

    code = "validation_error"
    http_status = 400


class NotReadyError(ApplicationError):
    """The runtime or one of its resources is not ready yet."""

    code = "not_ready"
    http_status = 503


class NotFoundError(ApplicationError):
    """The requested application object does not exist or is not cached."""

    code = "not_found"
    http_status = 404


class ConflictError(ApplicationError):
    """The requested operation conflicts with current state."""

    code = "conflict"
    http_status = 409


class OperationError(ApplicationError):
    """The operation could not be queued or completed."""

    code = "operation_failed"
    http_status = 503


class UnsupportedOperationError(ApplicationError):
    """The operation is valid in general but not supported by this build."""

    code = "unsupported_operation"
    http_status = 501


class StorageError(ApplicationError):
    """The local storage backend failed to read or write."""

    code = "storage_error"
    http_status = 500


class DataDirectoryError(ApplicationError):
    """The configured data directory cannot be created or written."""

    code = "data_directory_error"
    http_status = 500
