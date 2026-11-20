"""
PubSub / GossipSub endpoints.

GET /api/v1/pubsub/peers         - all peers connected via PubSub
GET /api/v1/pubsub/mesh          - GossipSub mesh per topic
GET /api/v1/pubsub/fanout        - GossipSub fanout per topic
GET /api/v1/pubsub/config        - GossipSub configuration values
GET /api/v1/pubsub/subscriptions - active subscription topic names
"""

from .base import BaseHandler


class PubSubPeersHandler(BaseHandler):
    """GET /api/v1/pubsub/peers"""

    def get(self) -> None:
        if not self.require_ready():
            return
        peers = self.discovery_service.pubsub_peers()
        self.send_success({"peers": peers, "count": len(peers)})


class PubSubMeshHandler(BaseHandler):
    """GET /api/v1/pubsub/mesh"""

    def get(self) -> None:
        if not self.require_ready():
            return
        mesh = self.discovery_service.mesh()
        total_peers = sum(len(v) for v in mesh.values())
        self.send_success({
            "mesh": mesh,
            "topic_count": len(mesh),
            "total_mesh_peers": total_peers,
        })


class PubSubFanoutHandler(BaseHandler):
    """GET /api/v1/pubsub/fanout"""

    def get(self) -> None:
        if not self.require_ready():
            return
        self.send_success({"fanout": self.discovery_service.fanout()})


class PubSubConfigHandler(BaseHandler):
    """GET /api/v1/pubsub/config"""

    def get(self) -> None:
        if not self.require_ready():
            return
        self.send_success(self.discovery_service.gossipsub_config())


class PubSubSubscriptionsHandler(BaseHandler):
    """GET /api/v1/pubsub/subscriptions"""

    def get(self) -> None:
        if not self.require_ready():
            return
        topics = self.discovery_service.subscriptions()
        self.send_success({"subscriptions": topics, "count": len(topics)})
