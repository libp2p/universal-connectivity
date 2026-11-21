"""
Base handler for all Tornado API endpoints.

Handlers talk to the shared ApplicationRuntime service layer, never directly to
libp2p components. This module owns the translation from application errors to
the HTTP envelope used by every endpoint.
"""

import json
import time
import logging
import traceback
from typing import Any

import tornado.web

from app.errors import ApplicationError

logger = logging.getLogger("api.base")


def as_runtime(candidate: Any) -> Any:
    """Return an ApplicationRuntime for ``candidate``.

    ``TornadoServer`` passes a runtime. Tests and older embedders may still pass
    a bare service object, so that case is wrapped once here instead of leaking
    service wiring into individual handlers.
    """
    from app.runtime import ApplicationRuntime

    if isinstance(candidate, ApplicationRuntime):
        return candidate
    if all(hasattr(candidate, name) for name in ("service", "peer", "messaging")):
        return candidate  # duck-typed runtime supplied by a test double

    # Bare engines (tests, older embedders) must still resolve to ONE runtime:
    # building a new one per request would give every handler its own event bus
    # and break "multiple adapters share the same instances".
    existing = getattr(candidate, "_uc_runtime", None)
    if isinstance(existing, ApplicationRuntime):
        return existing
    runtime = ApplicationRuntime(service=candidate)
    try:
        candidate._uc_runtime = runtime
    except Exception:  # pragma: no cover - slotted/duck-typed engines
        pass
    return runtime

def parse_string_field(
    body: dict[str, Any],
    field: str,
    default: str = "",
    required: bool = False,
    max_length: int | None = None,
) -> str:
    """
    Extract a string field from a parsed JSON object.

    ``get_json_body()`` guarantees a dict, but it does not constrain the value
    types. Calling ``.strip()`` on an arbitrary JSON value (for example an int)
    raises AttributeError and turns a client mistake into a 500. This helper
    gives every handler the same 400-friendly validation instead.

    Raises:
        ValueError: with a message that is safe to return to the client.
    """
    value = body.get(field, default)
    if not isinstance(value, str):
        raise ValueError(f"'{field}' must be a string.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"'{field}' field is required.")
    if max_length is not None and len(value) > max_length:
        raise ValueError(f"'{field}' must be at most {max_length} characters.")
    return value


class BaseHandler(tornado.web.RequestHandler):
    """Base class for all REST API handlers."""

    runtime: Any
    service: Any

    def initialize(self, runtime: Any) -> None:
        """Inject the shared ApplicationRuntime (or a bare service)."""
        self.runtime = as_runtime(runtime)
        # Kept for compatibility with embedders that still reach for the engine.
        self.service = self.runtime.service

    # Convenience accessors used by handlers.
    @property
    def peer_service(self) -> Any:
        return self.runtime.peer

    @property
    def connection_service(self) -> Any:
        return self.runtime.connections

    @property
    def messaging_service(self) -> Any:
        return self.runtime.messaging

    @property
    def discovery_service(self) -> Any:
        return self.runtime.discovery

    @property
    def identity_service(self) -> Any:
        return self.runtime.identity

    @property
    def file_service(self) -> Any:
        return self.runtime.files

    @property
    def storage_service(self) -> Any:
        return self.runtime.storage

    # ------------------------------------------------------------------ #
    #  CORS                                                                #
    # ------------------------------------------------------------------ #
    def set_default_headers(self) -> None:
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.set_header("Content-Type", "application/json")

    def options(self, *args: str, **kwargs: str) -> None:
        """Handle CORS preflight."""
        self.set_status(204)
        self.finish()

    # ------------------------------------------------------------------ #
    #  JSON helpers                                                        #
    # ------------------------------------------------------------------ #
    def send_success(self, data: Any = None, status: int = 200) -> None:
        self.set_status(status)
        self.finish(json.dumps({
            "success": True,
            "data": data,
            "error": None,
            "timestamp": time.time(),
        }))

    def send_error_response(
        self,
        message: str,
        status: int = 400,
        detail: str | None = None,
    ) -> None:
        self.set_status(status)
        self.finish(json.dumps({
            "success": False,
            "data": None,
            "error": {
                "code": status,
                "message": message,
                "detail": detail,
            },
            "timestamp": time.time(),
        }))

    # ------------------------------------------------------------------ #
    #  Request body helpers                                                #
    # ------------------------------------------------------------------ #
    def get_json_body(self) -> dict[str, Any]:
        try:
            body = json.loads(self.request.body)
        except Exception:
            return {}
        # Handlers always call .get() on the result, so a bare JSON array or
        # scalar must not leak through as a non-dict.
        return body if isinstance(body, dict) else {}

    # ------------------------------------------------------------------ #
    #  Service readiness guard                                             #
    # ------------------------------------------------------------------ #
    def require_ready(self) -> bool:
        """Return False and send 503 if the runtime is not ready yet."""
        if not self.runtime.ready:
            self.send_error_response(
                "Service not ready yet — the peer is still initialising.",
                status=503,
            )
            return False
        return True

    def require_topic(self, topic: str) -> bool:
        """Return False and send 404 unless ``topic`` is subscribed."""
        if topic not in self.messaging_service.subscribed_topics():
            self.send_error_response(
                f"Topic '{topic}' not found or not subscribed.",
                status=404,
            )
            return False
        return True

    # ------------------------------------------------------------------ #
    #  Application error translation                                       #
    # ------------------------------------------------------------------ #
    def _handle_request_exception(self, exc: BaseException) -> None:
        """Map service-layer errors onto the existing HTTP envelope.

        Services raise ApplicationError subclasses with an ``http_status``; the
        adapter is the only place that knows about HTTP.
        """
        if isinstance(exc, ApplicationError):
            logger.debug(
                "Application error on %s %s: %s",
                self.request.method,
                self.request.path,
                exc,
            )
            self.send_error_response(
                exc.message,
                status=exc.http_status,
                detail=exc.detail,
            )
            return
        super()._handle_request_exception(exc)

    # ------------------------------------------------------------------ #
    #  Global exception handler                                            #
    # ------------------------------------------------------------------ #
    def write_error(self, status_code: int, **kwargs: Any) -> None:
        exc_info = kwargs.get("exc_info")
        if exc_info:
            # Keep the traceback in the server log; do not expose internal
            # exception text to unauthenticated API clients on 5xx responses.
            logger.error("Unhandled API error (HTTP %s)", status_code, exc_info=exc_info)
        detail = None
        if exc_info and status_code < 500:
            detail = traceback.format_exception(*exc_info)[-1].strip()
        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps({
            "success": False,
            "data": None,
            "error": {
                "code": status_code,
                "message": self._reason,
                "detail": detail,
            },
            "timestamp": time.time(),
        }))
