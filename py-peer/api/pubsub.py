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

    def get(self):
        if not self.require_ready():
            return
        try:
            peers = [str(p) for p in self.service.pubsub.peers.keys()]
        except Exception as e:
            self.send_error_response(f"Could not read pubsub peers: {e}", status=500)
            return
        self.send_success({"peers": peers, "count": len(peers)})


class PubSubMeshHandler(BaseHandler):
    """GET /api/v1/pubsub/mesh"""

    def get(self):
        if not self.require_ready():
            return
        try:
            raw_mesh = getattr(self.service.gossipsub, "mesh", {})
            mesh = {
                topic: [str(p) for p in peers]
                for topic, peers in raw_mesh.items()
            }
            total_peers = sum(len(v) for v in mesh.values())
        except Exception as e:
            self.send_error_response(f"Could not read GossipSub mesh: {e}", status=500)
            return
        self.send_success({
            "mesh": mesh,
            "topic_count": len(mesh),
            "total_mesh_peers": total_peers,
        })


class PubSubFanoutHandler(BaseHandler):
    """GET /api/v1/pubsub/fanout"""

    def get(self):
        if not self.require_ready():
            return
        try:
            raw = getattr(self.service.gossipsub, "fanout", {})
            fanout = {
                topic: [str(p) for p in peers]
                for topic, peers in raw.items()
            }
        except Exception as e:
            self.send_error_response(f"Could not read GossipSub fanout: {e}", status=500)
            return
        self.send_success({"fanout": fanout})


class PubSubConfigHandler(BaseHandler):
    """GET /api/v1/pubsub/config"""

    def get(self):
        if not self.require_ready():
            return
        gs = self.service.gossipsub
        self.send_success({
            "degree": getattr(gs, "degree", None),
            "degree_low": getattr(gs, "degree_low", None),
            "degree_high": getattr(gs, "degree_high", None),
            "gossip_window": getattr(gs, "gossip_window", None),
            "gossip_history": getattr(gs, "gossip_history", None),
            "heartbeat_interval": getattr(gs, "heartbeat_interval", None),
            "heartbeat_initial_delay": getattr(gs, "heartbeat_initial_delay", None),
            "protocols": [str(p) for p in getattr(gs, "protocols", [])],
        })


class PubSubSubscriptionsHandler(BaseHandler):
    """GET /api/v1/pubsub/subscriptions"""

    def get(self):
        if not self.require_ready():
            return
        topics = list(self.service.get_subscribed_topics())
        self.send_success({"subscriptions": topics, "count": len(topics)})
