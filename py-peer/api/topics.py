"""
Topic / channel endpoints.

GET    /api/v1/topics              - list all subscribed topics with metadata
POST   /api/v1/topics              - subscribe to a new topic
GET    /api/v1/topics/{topic}/info - topic details (unread, total, last msg)
GET    /api/v1/topics/{topic}/peers - peers in GossipSub mesh for topic
"""

from typing import Any

from .base import BaseHandler, parse_string_field
from app.chatroom import MAX_TOPIC_NAME_LENGTH


def _sanitize_last_message(info: dict[str, Any]) -> dict[str, Any]:
    """Drop non-serialisable last_message values from legacy history entries."""
    if info.get("last_message") and not isinstance(info["last_message"], dict):
        info["last_message"] = None
    return info


class TopicListHandler(BaseHandler):
    """GET /api/v1/topics — POST /api/v1/topics"""

    def get(self) -> None:
        if not self.require_ready():
            return
        topics_info = self.discovery_service.topics()
        for info in topics_info.values():
            _sanitize_last_message(info)
        self.send_success({"topics": topics_info, "count": len(topics_info)})

    def post(self) -> None:
        if not self.require_ready():
            return
        body = self.get_json_body()
        try:
            topic = parse_string_field(
                body,
                "topic",
                required=True,
                max_length=MAX_TOPIC_NAME_LENGTH,
            )
        except ValueError as e:
            self.send_error_response(str(e))
            return
        self.send_success(self.discovery_service.subscribe(topic), status=202)


class TopicInfoHandler(BaseHandler):
    """GET /api/v1/topics/{topic}/info"""

    def get(self, topic: str) -> None:
        if not self.require_ready():
            return
        self.send_success(_sanitize_last_message(self.discovery_service.topic_info(topic)))


class TopicMeshPeersHandler(BaseHandler):
    """GET /api/v1/topics/{topic}/peers — peers in GossipSub mesh for topic"""

    def get(self, topic: str) -> None:
        if not self.require_ready():
            return
        if not self.require_topic(topic):
            return
        peers_in_mesh = self.discovery_service.mesh_peers(topic)
        self.send_success({
            "topic": topic,
            "mesh_peers": peers_in_mesh,
            "count": len(peers_in_mesh),
        })
