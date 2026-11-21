"""Shared application runtime.

One ``ApplicationRuntime`` owns exactly one ``HeadlessService`` (and therefore
one libp2p host) per process. Adapters receive this object and use its service
facades; they never construct a host or a service graph themselves.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import trio

from .errors import ApplicationError
from .events import Event, EventBus
from .models import RuntimeConfig, ServiceStatus
from .paths import DataPaths
from .services import ServiceBundle
from .storage import MemoryStore, open_store

logger = logging.getLogger("app.runtime")


class ApplicationRuntime:
    """Own the peer host, services, and event bus for one application."""

    def __init__(
        self,
        config: RuntimeConfig | None = None,
        *,
        service: Any = None,
        event_bus: Any = None,
        store: Any = None,
    ) -> None:
        if config is None and service is None:
            raise ValueError("ApplicationRuntime requires config= or service=")
        self.config = config
        self.events = event_bus or EventBus()
        self.paths: DataPaths | None = None

        if service is None:
            assert config is not None
            from .chatroom import configure_system_log
            from core.headless import HeadlessService

            # Resolve and prove the data directory before anything is written:
            # a bad path fails startup with one actionable error instead of a
            # half-configured node whose SQLite or key write fails later.
            self.paths = DataPaths.resolve(
                data_dir=config.data_dir, storage_path=config.storage_path
            ).ensure_writable()
            configure_system_log(self.paths.system_log_file)

            self.store = store or open_store(
                ":memory:"
                if self.paths.database_in_memory
                else str(self.paths.database_file)
            )
            self.service = HeadlessService(
                **config.service_kwargs(identity_path=str(self.paths.identity_file)),
                message_store=self.store,
            )
        else:
            self.service = service
            existing = getattr(service, "message_store", None)
            self.store = store or existing or MemoryStore()
            if existing is not self.store:
                try:
                    service.message_store = self.store
                except Exception:  # pragma: no cover - duck-typed test doubles
                    logger.debug("Attached service does not accept a message store")

        # Event publication is additive: HeadlessService publishes to this bus
        # while existing queue consumers keep working during the migration.
        try:
            self.service.event_bus = self.events
        except Exception:  # pragma: no cover - duck-typed test doubles
            logger.debug("Attached service does not accept an event bus")

        # The engine builds its own bundle in __init__; an injected service
        # (or a test double) gets one composed here. Adapters always talk to
        # these service instances, never to the engine's private methods.
        bundle = getattr(self.service, "services", None)
        if not isinstance(bundle, ServiceBundle):
            bundle = ServiceBundle(
                self.service, store=self.store, event_bus=self.events
            )
            try:
                self.service.services = bundle
            except Exception:  # pragma: no cover - duck-typed test doubles
                logger.debug("Attached service does not accept a service bundle")
        else:
            bundle.bind_store(self.store)
        self.bundle = bundle
        self.storage = bundle.storage
        self.peer = bundle.peers
        self.connections = bundle.connections
        self.messaging = bundle.messaging
        self.discovery = bundle.discovery
        self.identity = bundle.identity
        self.files = bundle.files

        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._start_attempted = False
        self._stop_requested = False
        self._started_at: float | None = None
        self._explicit_failure = False
        # Set once startup resolves either way (ready or the thread exits), so
        # start_in_thread can block instead of polling service.ready.
        self._startup_done = threading.Event()
        try:
            self.service.on_ready = self._startup_done.set
        except Exception:  # pragma: no cover - duck-typed test doubles
            logger.debug("Attached service does not accept an on_ready callback")

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #
    @property
    def ready(self) -> bool:
        return bool(getattr(self.service, "ready", False))

    @property
    def running(self) -> bool:
        return bool(getattr(self.service, "running", False))

    @property
    def failed(self) -> bool:
        return self._explicit_failure or bool(getattr(self.service, "failed", False))

    @property
    def stop_event(self) -> Any:
        return getattr(self.service, "stop_event", None)

    @property
    def thread(self) -> threading.Thread | None:
        return self._thread

    @property
    def state(self) -> str:
        if self.failed:
            return "failed"
        if self._stop_requested:
            if self._thread is not None and self._thread.is_alive():
                return "stopping"
            return "stopped"
        if self.ready:
            return "ready"
        if self._start_attempted:
            return "starting"
        return "created"

    @property
    def uptime_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        return round(max(0.0, time.monotonic() - self._started_at), 1)

    async def start(self) -> None:
        """Run the engine until stopped. Must be awaited inside a trio loop."""
        with self._lock:
            if self._start_attempted:
                raise RuntimeError(
                    "ApplicationRuntime.start() has already been called on this instance"
                )
            self._start_attempted = True
            self._started_at = time.monotonic()
        try:
            await self.service.start()
        except BaseException:
            self._explicit_failure = True
            raise
        finally:
            # Subscribers must not receive events after the runtime is gone;
            # closing the store here releases the SQLite file after the engine
            # has finished writing (teardown runs on the same trio task).
            self.events.close()
            self.store.close()

    def _thread_main(self) -> None:
        try:
            trio.run(self.start)
        except BaseException:
            # Startup failures are surfaced through service.failed / start_in_thread.
            logger.exception("Application runtime thread exited with an error")
        finally:
            # Wake a waiter even when startup failed before readiness.
            self._startup_done.set()

    def start_in_thread(self, timeout: float = 30.0) -> threading.Thread:
        """Start the runtime on a background trio thread and wait for readiness.

        Raises RuntimeError if the peer fails or does not become ready within
        ``timeout``; any partially started resources are cleaned up first.
        """
        with self._lock:
            if self._thread is not None or self._start_attempted:
                raise RuntimeError(
                    "ApplicationRuntime has already been started on this instance"
                )
        thread = threading.Thread(
            target=self._thread_main, name="uc-runtime", daemon=True
        )
        with self._lock:
            self._thread = thread
        thread.start()

        # Block until the engine signals readiness or the thread exits; no
        # sleep loop, and a startup failure returns immediately.
        self._startup_done.wait(timeout)

        if self.failed:
            self._stop_and_join(timeout=10.0)
            raise RuntimeError("Application runtime failed to start")
        if not self.ready:
            self._stop_and_join(timeout=10.0)
            raise RuntimeError(
                f"Application runtime failed to start within {timeout:.0f}s"
            )
        logger.info("Application runtime is ready")
        return thread

    def request_stop(self) -> None:
        """Signal shutdown from any thread. Teardown runs on the trio thread."""
        self._stop_requested = True
        request_stop = getattr(self.service, "request_stop", None)
        if request_stop is not None:
            request_stop()
        else:  # pragma: no cover - defensive for test doubles
            stop_event = self.stop_event
            if stop_event is not None:
                stop_event.set()

    async def stop(self) -> None:
        """Async stop request; kept for callers already inside the trio loop."""
        self.request_stop()

    def join(self, timeout: float = 10.0) -> bool:
        """Wait for the runtime thread to finish. True when it is gone."""
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def _stop_and_join(self, timeout: float = 10.0) -> bool:
        self.request_stop()
        return self.join(timeout)

    def close(self) -> None:
        """Release adapter-side resources (event subscriptions)."""
        self.events.close()

    # ------------------------------------------------------------------ #
    #  Status / configuration
    # ------------------------------------------------------------------ #
    def status(self) -> ServiceStatus:
        peer_id = None
        multiaddrs: list[str] = []
        listen_addrs: list[str] = []
        peer_count = 0
        if self.ready:
            try:
                info = self.peer.connection_info()
                peer_id = info.peer_id
                multiaddrs = list(info.multiaddrs)
                listen_addrs = list(info.listen_addrs)
                peer_count = info.peer_count
            except Exception:  # pragma: no cover - engine teardown race
                logger.debug("Could not read connection info for status", exc_info=True)
        return ServiceStatus(
            state=self.state,
            ready=self.ready,
            running=self.running,
            failed=self.failed,
            peer_id=peer_id,
            nickname=getattr(self.service, "nickname", ""),
            port=getattr(self.service, "port", 0),
            topic=getattr(self.service, "topic", None),
            strict_signing=bool(getattr(self.service, "strict_signing", True)),
            uptime_seconds=self.uptime_seconds,
            peer_count=peer_count,
            multiaddrs=multiaddrs,
            listen_addrs=listen_addrs,
        )

    def config_snapshot(self) -> dict[str, Any]:
        service = self.service
        return {
            "nickname": getattr(service, "nickname", ""),
            "port": getattr(service, "port", 0),
            "topic": getattr(service, "topic", None),
            "strict_signing": bool(getattr(service, "strict_signing", True)),
            "download_dir": getattr(service, "download_dir", ""),
            "connect_addrs": list(getattr(service, "connect_addrs", []) or []),
            "listen_addrs": list(getattr(service, "transport_addrs", []) or []),
            "announce_addrs": list(getattr(service, "full_multiaddrs", []) or []),
            "storage": self.storage.health(),
            "data_dir": str(self.paths.root) if self.paths else None,
            "identity_file": (
                str(self.paths.identity_file) if self.paths else None
            ),
            "identity_source": getattr(service, "identity_source", None),
        }

    # ------------------------------------------------------------------ #
    #  Events
    # ------------------------------------------------------------------ #
    def subscribe(self, types: Any = None, maxsize: Any = None) -> Any:
        return self.events.subscribe(types=types, maxsize=maxsize)

    def unsubscribe(self, subscription: Any) -> None:
        self.events.unsubscribe(subscription)

    def publish(self, event: Event) -> None:
        self.events.publish(event)


__all__ = ["ApplicationRuntime", "RuntimeConfig", "ApplicationError"]
