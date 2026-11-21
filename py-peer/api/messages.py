"""
Messaging endpoints.

POST /api/v1/messages                  - send to default chat topic
POST /api/v1/messages/{topic}          - send to specific topic
GET  /api/v1/messages/{topic}          - retrieve stored messages (paginated)
GET  /api/v1/messages/{topic}/unread   - unread count
PUT  /api/v1/messages/{topic}/read     - mark all as read
"""

from .base import BaseHandler, parse_string_field


class SendDefaultMessageHandler(BaseHandler):
    """POST /api/v1/messages — sends to the node's default chat topic"""

    def post(self) -> None:
        if not self.require_ready():
            return
        body = self.get_json_body()
        try:
            msg = parse_string_field(body, "message", required=True)
        except ValueError as e:
            self.send_error_response(str(e))
            return
        self.messaging_service.send(msg)
        self.send_success({"message": "Message queued for delivery"}, status=202)


class TopicMessagesHandler(BaseHandler):
    """
    GET  /api/v1/messages/{topic}  — list stored messages
    POST /api/v1/messages/{topic}  — send a message to this topic
    """

    def get(self, topic: str) -> None:
        if not self.require_ready():
            return
        if not self.require_topic(topic):
            return
        try:
            limit = int(self.get_argument("limit", "100"))
            offset = int(self.get_argument("offset", "0"))
        except ValueError:
            self.send_error_response("'limit' and 'offset' must be integers.")
            return
        self.send_success(self.storage_service.history(topic, limit=limit, offset=offset))

    def post(self, topic: str) -> None:
        if not self.require_ready():
            return
        body = self.get_json_body()
        try:
            msg = parse_string_field(body, "message", required=True)
        except ValueError as e:
            self.send_error_response(str(e))
            return
        self.messaging_service.send_to_topic(topic, msg)
        self.send_success(
            {"message": "Message queued for delivery", "topic": topic}, status=202
        )


class TopicUnreadHandler(BaseHandler):
    """GET /api/v1/messages/{topic}/unread"""

    def get(self, topic: str) -> None:
        if not self.require_ready():
            return
        if not self.require_topic(topic):
            return
        count = self.messaging_service.unread_count(topic)
        self.send_success({"topic": topic, "unread_count": count})


class TopicMarkReadHandler(BaseHandler):
    """PUT /api/v1/messages/{topic}/read"""

    def put(self, topic: str) -> None:
        if not self.require_ready():
            return
        if not self.require_topic(topic):
            return
        self.messaging_service.mark_read(topic)
        self.send_success({"topic": topic, "message": "All messages marked as read"})
