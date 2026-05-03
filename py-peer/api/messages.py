"""
Messaging endpoints.

POST /api/v1/messages                  - send to default chat topic
POST /api/v1/messages/{topic}          - send to specific topic
GET  /api/v1/messages/{topic}          - retrieve stored messages (paginated)
GET  /api/v1/messages/{topic}/unread   - unread count
PUT  /api/v1/messages/{topic}/read     - mark all as read
"""

from .base import BaseHandler


class SendDefaultMessageHandler(BaseHandler):
    """POST /api/v1/messages — sends to the node's default chat topic"""

    def post(self):
        if not self.require_ready():
            return
        body = self.get_json_body()
        msg = body.get("message", "").strip()
        if not msg:
            self.send_error_response("'message' field is required.")
            return
        self.service.send_message(msg)
        self.send_success({"message": "Message queued for delivery"}, status=202)


class TopicMessagesHandler(BaseHandler):
    """
    GET  /api/v1/messages/{topic}  — list stored messages
    POST /api/v1/messages/{topic}  — send a message to this topic
    """

    def get(self, topic):
        if not self.require_ready():
            return
        try:
            limit = int(self.get_argument("limit", 100))
            offset = int(self.get_argument("offset", 0))
        except ValueError:
            self.send_error_response("'limit' and 'offset' must be integers.")
            return

        all_msgs = self.service.get_topic_messages(topic)
        page = all_msgs[offset: offset + limit]
        self.send_success({
            "topic": topic,
            "messages": page,
            "total": len(all_msgs),
            "limit": limit,
            "offset": offset,
        })

    def post(self, topic):
        if not self.require_ready():
            return
        body = self.get_json_body()
        msg = body.get("message", "").strip()
        if not msg:
            self.send_error_response("'message' field is required.")
            return

        # Check topic is subscribed
        subscribed = self.service.get_subscribed_topics()
        if topic not in subscribed:
            self.send_error_response(
                f"Not subscribed to topic '{topic}'. Subscribe first via POST /api/v1/topics.",
                status=400,
            )
            return

        self.service.send_message_to_topic(topic, msg)
        self.send_success({"message": "Message queued for delivery", "topic": topic}, status=202)


class TopicUnreadHandler(BaseHandler):
    """GET /api/v1/messages/{topic}/unread"""

    def get(self, topic):
        if not self.require_ready():
            return
        count = self.service.get_unread_count(topic)
        self.send_success({"topic": topic, "unread_count": count})


class TopicMarkReadHandler(BaseHandler):
    """PUT /api/v1/messages/{topic}/read"""

    def put(self, topic):
        if not self.require_ready():
            return
        self.service.mark_topic_as_read(topic)
        self.send_success({"topic": topic, "message": "All messages marked as read"})
