"""
Tornado REST + WebSocket server for the py-peer Universal Connectivity DApp.

Routes all API requests to the appropriate handlers, injects the HeadlessService
via handler `initialize()`, and runs the asyncio IOLoop in the main thread while
HeadlessService runs on a trio event loop in a background thread.

Usage
-----
Instantiate TornadoServer and call start():

    from tornado_server import TornadoServer
    server = TornadoServer(headless_service, port=8765)
    server.start()          # blocks — runs Tornado IOLoop
"""

import logging
import sys

import tornado.ioloop
import tornado.web

from api.node      import NodeInfoHandler, NodeStatusHandler, NodeMultiaddrHandler
from api.peers     import (PeerListHandler, PeerCountHandler, KnownPeersHandler,
                           PeerConnectHandler, PeerDetailHandler, PeerIdentifyHandler)
from api.messages  import (SendDefaultMessageHandler, TopicMessagesHandler,
                           TopicUnreadHandler, TopicMarkReadHandler)
from api.topics    import TopicListHandler, TopicInfoHandler, TopicMeshPeersHandler
from api.files     import (SharedFilesHandler, SharedFileDetailHandler,
                           ShareFileHandler, DownloadFileHandler, UploadAndShareHandler)
from api.dht       import DHTStatusHandler, DHTPeersHandler, DHTRoutingTableHandler
from api.pubsub    import (PubSubPeersHandler, PubSubMeshHandler, PubSubFanoutHandler,
                           PubSubConfigHandler, PubSubSubscriptionsHandler)
from api.identity  import (IdentityCacheListHandler, IdentityPeerHandler,
                           IdentityPublicKeyHandler, IdentityCacheDeleteHandler)
from api.service   import (ServiceStatusHandler, ServiceConfigHandler,
                           ServiceStopHandler, ServiceBootstrapHandler)
from api.websocket import (MessageStreamHandler, SystemStreamHandler,
                           PeerUpdateHandler, MeshUpdateHandler)
from rag_handler import AskHandler, load_vectorstore

logger = logging.getLogger("tornado_server")

DEFAULT_API_PORT = 8765


def _make_app(service, vectorstore=None) -> tornado.web.Application:
    """Build and return the Tornado Application with all routes."""

    kw = dict(service=service)   # kwargs passed to every handler's initialize()

    routes = [
        # ── Node ────────────────────────────────────────────────────────
        (r"/api/v1/node/info",      NodeInfoHandler,     kw),
        (r"/api/v1/node/status",    NodeStatusHandler,   kw),
        (r"/api/v1/node/multiaddr", NodeMultiaddrHandler, kw),

        # ── Peers ────────────────────────────────────────────────────────
        (r"/api/v1/peers",                    PeerListHandler,     kw),
        (r"/api/v1/peers/count",              PeerCountHandler,    kw),
        (r"/api/v1/peers/known",              KnownPeersHandler,   kw),
        (r"/api/v1/peers/connect",            PeerConnectHandler,  kw),
        (r"/api/v1/peers/([^/]+)/identify",   PeerIdentifyHandler, kw),
        (r"/api/v1/peers/([^/]+)",            PeerDetailHandler,   kw),

        # ── Messages ─────────────────────────────────────────────────────
        (r"/api/v1/messages",                         SendDefaultMessageHandler, kw),
        (r"/api/v1/messages/([^/]+)/unread",          TopicUnreadHandler,        kw),
        (r"/api/v1/messages/([^/]+)/read",            TopicMarkReadHandler,      kw),
        (r"/api/v1/messages/([^/]+)",                 TopicMessagesHandler,      kw),

        # ── Topics ───────────────────────────────────────────────────────
        (r"/api/v1/topics",                   TopicListHandler,      kw),
        (r"/api/v1/topics/([^/]+)/info",      TopicInfoHandler,      kw),
        (r"/api/v1/topics/([^/]+)/peers",     TopicMeshPeersHandler, kw),

        # ── Files ────────────────────────────────────────────────────────
        (r"/api/v1/files/shared",             SharedFilesHandler,       kw),
        (r"/api/v1/files/shared/([^/]+)",     SharedFileDetailHandler,  kw),
        (r"/api/v1/files/share",              ShareFileHandler,          kw),
        (r"/api/v1/files/download",           DownloadFileHandler,       kw),
        (r"/api/v1/files/upload",             UploadAndShareHandler,     kw),

        # ── DHT ──────────────────────────────────────────────────────────
        (r"/api/v1/dht/status",        DHTStatusHandler,       kw),
        (r"/api/v1/dht/peers",         DHTPeersHandler,        kw),
        (r"/api/v1/dht/routing-table", DHTRoutingTableHandler, kw),

        # ── PubSub ───────────────────────────────────────────────────────
        (r"/api/v1/pubsub/peers",         PubSubPeersHandler,        kw),
        (r"/api/v1/pubsub/mesh",          PubSubMeshHandler,         kw),
        (r"/api/v1/pubsub/fanout",        PubSubFanoutHandler,       kw),
        (r"/api/v1/pubsub/config",        PubSubConfigHandler,       kw),
        (r"/api/v1/pubsub/subscriptions", PubSubSubscriptionsHandler, kw),

        # ── Identity ─────────────────────────────────────────────────────
        (r"/api/v1/identity/cache",                IdentityCacheListHandler,   kw),
        (r"/api/v1/identity/([^/]+)/pubkey",       IdentityPublicKeyHandler,   kw),
        (r"/api/v1/identity/([^/]+)/cache",        IdentityCacheDeleteHandler, kw),
        (r"/api/v1/identity/([^/]+)",              IdentityPeerHandler,        kw),

        # ── Service ──────────────────────────────────────────────────────
        (r"/api/v1/service/status",    ServiceStatusHandler,    kw),
        (r"/api/v1/service/config",    ServiceConfigHandler,    kw),
        (r"/api/v1/service/stop",      ServiceStopHandler,      kw),
        (r"/api/v1/service/bootstrap", ServiceBootstrapHandler, kw),
        # ── RAG assistant ───────────────────────────────────────────────
        (r"/api/v1/ask",  AskHandler, dict(vectorstore=vectorstore)),
        # ── WebSockets ───────────────────────────────────────────────────
        (r"/ws/messages",    MessageStreamHandler, kw),
        (r"/ws/system",      SystemStreamHandler,  kw),
        (r"/ws/peers",       PeerUpdateHandler,    kw),
        (r"/ws/pubsub/mesh", MeshUpdateHandler,    kw),
    ]

    return tornado.web.Application(
        routes,
        debug=False,
        # Allow large file uploads (100 MB)
        max_body_size=100 * 1024 * 1024,
    )


class TornadoServer:
    """
    Wraps the Tornado Application and IOLoop.

    Parameters
    ----------
    service : HeadlessService
        The running (or still-starting) headless service.
    port : int
        HTTP port to listen on (default 8765).
    """

    def __init__(self, service, port: int = DEFAULT_API_PORT):
        self.service = service
        self.port = port
        vectorstore = load_vectorstore()
        self._app = _make_app(service, vectorstore=vectorstore)

    def start(self):
        """Start Tornado — blocks until the process is killed."""
        self._app.listen(self.port)
        logger.info(f"🌪  Tornado API server started on http://0.0.0.0:{self.port}")
        logger.info(f"    REST : http://localhost:{self.port}/api/v1/node/info")
        logger.info(f"    WS   : ws://localhost:{self.port}/ws/messages")
        try:
            tornado.ioloop.IOLoop.current().start()
        except KeyboardInterrupt:
            logger.info("Tornado server stopped.")
            tornado.ioloop.IOLoop.current().stop()


def _print_routes(port=DEFAULT_API_PORT):
    """Pretty-print all available API routes."""
    routes = [
        ("GET",    f"/api/v1/node/info",               "Node info (peer_id, multiaddr, nickname)"),
        ("GET",    f"/api/v1/node/status",              "Readiness, uptime"),
        ("GET",    f"/api/v1/node/multiaddr",           "Full multiaddr string"),
        ("GET",    f"/api/v1/peers",                    "Connected peers list"),
        ("GET",    f"/api/v1/peers/count",              "Connected peer count"),
        ("GET",    f"/api/v1/peers/known",              "All peers in peerstore"),
        ("POST",   f"/api/v1/peers/connect",            "Connect via multiaddr"),
        ("GET",    f"/api/v1/peers/{{peer_id}}",        "Peer peerstore info"),
        ("GET",    f"/api/v1/peers/{{peer_id}}/identify","Cached identify info"),
        ("POST",   f"/api/v1/messages",                 "Send to default chat topic"),
        ("GET",    f"/api/v1/messages/{{topic}}",       "List stored messages"),
        ("POST",   f"/api/v1/messages/{{topic}}",       "Send to specific topic"),
        ("GET",    f"/api/v1/messages/{{topic}}/unread","Unread count"),
        ("PUT",    f"/api/v1/messages/{{topic}}/read",  "Mark as read"),
        ("GET",    f"/api/v1/topics",                   "List subscribed topics"),
        ("POST",   f"/api/v1/topics",                   "Subscribe to new topic"),
        ("GET",    f"/api/v1/topics/{{topic}}/info",    "Topic details"),
        ("GET",    f"/api/v1/topics/{{topic}}/peers",   "Mesh peers for topic"),
        ("GET",    f"/api/v1/files/shared",             "List shared files"),
        ("GET",    f"/api/v1/files/shared/{{cid}}",     "Shared file detail"),
        ("POST",   f"/api/v1/files/share",              "Share local file"),
        ("POST",   f"/api/v1/files/download",           "Download file by CID"),
        ("POST",   f"/api/v1/files/upload",             "Upload + share (multipart)"),
        ("GET",    f"/api/v1/dht/status",               "DHT mode & routing table size"),
        ("GET",    f"/api/v1/dht/peers",                "DHT routing table peers"),
        ("GET",    f"/api/v1/dht/routing-table",        "Full routing table"),
        ("GET",    f"/api/v1/pubsub/peers",             "PubSub connected peers"),
        ("GET",    f"/api/v1/pubsub/mesh",              "GossipSub mesh state"),
        ("GET",    f"/api/v1/pubsub/fanout",            "GossipSub fanout"),
        ("GET",    f"/api/v1/pubsub/config",            "GossipSub config"),
        ("GET",    f"/api/v1/pubsub/subscriptions",     "Active subscriptions"),
        ("GET",    f"/api/v1/identity/cache",           "All cached identify entries"),
        ("GET",    f"/api/v1/identity/{{peer_id}}",     "Cached identify info"),
        ("GET",    f"/api/v1/identity/{{peer_id}}/pubkey","Public key (hex)"),
        ("DELETE", f"/api/v1/identity/{{peer_id}}/cache","Invalidate cache entry"),
        ("GET",    f"/api/v1/service/status",           "Service health"),
        ("GET",    f"/api/v1/service/config",           "Service config"),
        ("POST",   f"/api/v1/service/stop",             "Graceful stop"),
        ("POST",   f"/api/v1/service/bootstrap",        "Re-trigger bootstrap"),
        ("POST",   f"/api/v1/ask",                      "RAG assistant — ask about py-libp2p"),
        ("WS",     f"/ws/messages",                     "Real-time message stream"),
        ("WS",     f"/ws/system",                       "Real-time system events"),
        ("WS",     f"/ws/peers",                        "Real-time peer updates"),
        ("WS",     f"/ws/pubsub/mesh",                  "Real-time mesh topology"),
    ]
    print(f"\n{'='*70}")
    print(f" Tornado API  —  http://localhost:{port}")
    print(f"{'='*70}")
    for method, path, desc in routes:
        print(f"  {method:<7} {path:<44} {desc}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    # Quick standalone test — no real HeadlessService
    logging.basicConfig(level=logging.INFO)
    _print_routes()
    print("Run with: python main.py --nick alice --api --api-port 8765")
