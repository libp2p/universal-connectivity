"""Chat room lifecycle, message handling, and publishing.

The engine still creates the underlying libp2p host; this service owns the
application-level chat room: joining topics, converting inbound frames into
stored/notified messages, and draining the outgoing publish queue.
"""

from __future__ import annotations

import json
import logging
import time
from queue import Empty, Full
from typing import Any

import trio

from ..chatroom import ChatMessage, ChatRoom

from ..constants import FILE_MESSAGE_PREFIX
from ..errors import NotReadyError, OperationError, ValidationError

# One chat message is a bounded UI payload, not a file transfer. Files use the
# separate upload/share endpoints (25 MB cap). Keeping this limit in the
# service means direct, HTTP, and UI adapters all reject the same input.
MAX_MESSAGE_LENGTH = 4096

logger = logging.getLogger("app.services.messaging")


class MessagingService:
    """Own the chat room, inbound storage, and outbound publish queue."""

    def __init__(
        self,
        engine: Any,
        storage: Any,
        notifications: Any = None,
        identity: Any = None,
    ) -> None:
        self._engine = engine
        self._storage = storage
        self._notifications = notifications
        self._identity = identity

    @property
    def engine(self) -> Any:
        return self._engine

    @property
    def storage(self) -> Any:
        return self._storage

    # ------------------------------------------------------------------ #
    #  Input validation / API-facing operations
    # ------------------------------------------------------------------ #
    @staticmethod
    def validate_message(message: str) -> str:
        if not isinstance(message, str) or not message.strip():
            raise ValidationError("'message' field is required.")
        text = message.strip()
        if len(text) > MAX_MESSAGE_LENGTH:
            raise ValidationError(
                f"'message' must be at most {MAX_MESSAGE_LENGTH} characters."
            )
        return text

    def send(self, message: str) -> None:
        """Queue a message for the node's default chat topic."""
        text = self.validate_message(message)
        if not getattr(self._engine, "ready", False):
            raise NotReadyError("Service not ready — cannot queue a message.")
        if not self.enqueue(text):
            raise OperationError("Failed to queue message.")

    def send_to_topic(self, topic: str, message: str) -> None:
        """Queue a message for a subscribed topic."""
        text = self.validate_message(message)
        if not getattr(self._engine, "ready", False):
            raise NotReadyError("Service not ready — cannot queue a message.")
        if topic not in self.subscribed_topics():
            raise ValidationError(
                f"Not subscribed to topic '{topic}'. Subscribe first via POST "
                "/api/v1/topics."
            )
        if not self.enqueue_to_topic(topic, text):
            raise OperationError("Failed to queue message.")

    def history(
        self, topic: str, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        return self._storage.history(topic, limit=limit, offset=offset)

    def unread_count(self, topic: str) -> int:
        return self._storage.unread(topic)

    def mark_read(self, topic: str) -> None:
        self._storage.mark_read(topic)

    def subscribed_topics(self) -> set[str]:
        chat_room = getattr(self._engine, "chat_room", None)
        if chat_room is not None:
            return set(chat_room.get_subscribed_topics())
        if hasattr(self._engine, "get_subscribed_topics"):
            return set(self._engine.get_subscribed_topics())
        return set()

    def all_pubsub_topics(self) -> set[str]:
        chat_room = getattr(self._engine, "chat_room", None)
        if chat_room is not None:
            return set(chat_room.get_all_subscriptions())
        if hasattr(self._engine, "get_all_pubsub_topics"):
            return set(self._engine.get_all_pubsub_topics())
        return set()

    def connected_peers(self) -> set[str]:
        chat_room = getattr(self._engine, "chat_room", None)
        if chat_room is None:
            return set()
        return set(chat_room.get_connected_peers())

    def peer_count(self) -> int:
        chat_room = getattr(self._engine, "chat_room", None)
        return chat_room.get_peer_count() if chat_room else 0

    # ------------------------------------------------------------------ #
    #  Queueing (thread-safe wrappers used by adapters)
    # ------------------------------------------------------------------ #
    def enqueue(self, message: str) -> bool:
        """Queue a message for the default chat topic."""
        queue = getattr(self._engine, "outgoing_queue", None)
        if queue and getattr(self._engine, "running", False):
            try:
                queue.sync_q.put_nowait(
                    {"message": message, "timestamp": time.time()}
                )
                return True
            except Full:
                logger.warning("Outgoing message queue is full; dropping message")
            except Exception as e:
                logger.error(f"Failed to queue message: {e}")
        elif hasattr(self._engine, "send_message") and callable(self._engine.send_message):
            return bool(self._engine.send_message(message))
        else:
            logger.warning(
                "Cannot send message: outgoing queue not ready or service not running"
            )
        return False

    def enqueue_to_topic(self, topic: str, message: str) -> bool:
        """Queue a message for a specific topic."""
        queue = getattr(self._engine, "outgoing_queue", None)
        if queue and getattr(self._engine, "running", False):
            try:
                queue.sync_q.put_nowait(
                    {
                        "message": message,
                        "topic": topic,
                        "timestamp": time.time(),
                    }
                )
                return True
            except Full:
                logger.warning(
                    f"Outgoing message queue is full; dropping message for {topic}"
                )
            except Exception as e:
                logger.error(f"Failed to queue message to topic {topic}: {e}")
        elif hasattr(self._engine, "send_message_to_topic") and callable(self._engine.send_message_to_topic):
            return bool(self._engine.send_message_to_topic(topic, message))
        else:
            logger.warning(
                "Cannot send message: outgoing queue not ready or service not running"
            )
        return False

    # ------------------------------------------------------------------ #
    #  Chat room lifecycle
    # ------------------------------------------------------------------ #
    async def setup_chat_room(self) -> None:
        """Create and join the chat room, then start accepting messages."""
        logger.info("Setting up chat room...")

        self._engine.chat_room = await ChatRoom.join_chat_room(
            host=self._engine.host,
            pubsub=self._engine.pubsub,
            nickname=self._engine.nickname,
            multiaddr=self._engine.full_multiaddr,
            headless_service=self._engine,
            topic=self._engine.topic,
        )

        self._engine.chat_room.add_message_handler(self.handle_chat_message)
        self._engine.running = True

        logger.info(f"Chat room setup complete for '{self._engine.nickname}'")
        await self._system(f"Joined chat room as '{self._engine.nickname}'")

    async def stop_chat_room(self) -> None:
        chat_room = getattr(self._engine, "chat_room", None)
        if chat_room is None:
            return
        try:
            await chat_room.stop()
        except Exception:
            logger.exception("Error stopping ChatRoom")

    # ------------------------------------------------------------------ #
    #  Incoming messages
    # ------------------------------------------------------------------ #
    async def handle_chat_message(self, message: ChatMessage) -> None:
        """Store an incoming chat frame and fan it out to adapters."""
        try:
            engine = self._engine
            topic = message.topic or "default"

            # Our own messages are echoed back by GossipSub. They must not show
            # up as unread, or every message you send increments your own badge.
            is_own_message = bool(engine.host) and message.sender_id == str(
                engine.host.get_id()
            )
            is_file_message = message.message.startswith(FILE_MESSAGE_PREFIX)
            message_data: dict[str, Any]

            if is_file_message:
                try:
                    file_meta_json = message.message[len(FILE_MESSAGE_PREFIX):]
                    file_meta = json.loads(file_meta_json)
                    message_data = {
                        "type": "file_message",
                        "message": message.message,
                        "sender_nick": message.sender_nick,
                        "sender_id": message.sender_id,
                        "timestamp": message.timestamp,
                        "topic": topic,
                        "read": is_own_message,
                        "file_cid": file_meta.get("cid", ""),
                        "file_name": file_meta.get("filename", "unknown"),
                        "file_size": file_meta.get("filesize", 0),
                    }
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse file message: {e}")
                    message_data = {
                        "type": "chat_message",
                        "message": message.message,
                        "sender_nick": message.sender_nick,
                        "sender_id": message.sender_id,
                        "timestamp": message.timestamp,
                        "topic": topic,
                        "read": is_own_message,
                    }
            else:
                message_data = {
                    "type": "chat_message",
                    "message": message.message,
                    "sender_nick": message.sender_nick,
                    "sender_id": message.sender_id,
                    "timestamp": message.timestamp,
                    "topic": topic,
                    "read": is_own_message,
                }

            if getattr(message, "message_id", None):
                message_data["message_id"] = message.message_id

            if not await self._storage.append_message(message_data):
                logger.debug(
                    "Dropping duplicate message %s", message_data["message_id"]
                )
                return

            if not engine.ui_mode:
                if is_file_message:
                    logger.info(
                        f"[{topic}] {message.sender_nick} shared a file: "
                        f"{message_data.get('file_name', 'unknown')}"
                    )
                else:
                    logger.info(
                        f"[{topic}] {message.sender_nick}: {message.message}"
                    )

            if self._notifications is not None:
                self._notifications.message(message_data)
                self._notifications.publish_event(
                    "message_received", message_data
                )

        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            logger.exception("Full traceback:")

    # ------------------------------------------------------------------ #
    #  Workers
    # ------------------------------------------------------------------ #
    async def process_incoming(self) -> None:
        """Run the chat room's message handlers until cancelled."""
        try:
            if self._engine.chat_room is not None:
                await self._engine.chat_room.start_message_handlers()
        except Exception as e:
            logger.error(f"Error in message processing: {e}")

    async def process_outgoing(self) -> None:
        """Drain the outgoing queue and publish to the chat room."""
        while getattr(self._engine, "running", False):
            queue = getattr(self._engine, "outgoing_queue", None)
            if queue is None:
                await trio.sleep(0.1)
                continue
            try:
                try:
                    outgoing_data = queue.sync_q.get_nowait()
                    if outgoing_data and "message" in outgoing_data:
                        message = outgoing_data["message"]
                        topic = outgoing_data.get("topic")

                        if self._engine.chat_room and self._engine.running:
                            if topic:
                                await self._engine.chat_room.publish_to_topic(
                                    topic, message
                                )
                                if not self._engine.ui_mode:
                                    logger.info(
                                        f"{self._engine.nickname} (you) to {topic}: "
                                        f"{message}"
                                    )
                            else:
                                await self._engine.chat_room.publish_message(
                                    message
                                )
                                if not self._engine.ui_mode:
                                    logger.info(
                                        f"{self._engine.nickname} (you): {message}"
                                    )
                        else:
                            logger.warning(
                                "Cannot send message: chat room not ready"
                            )
                            await self._system(
                                "Cannot send message: chat room not ready"
                            )

                except Empty:
                    await trio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error processing outgoing message: {e}")
                    await trio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in outgoing message processing: {e}")
                await trio.sleep(0.1)

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    async def _system(self, message: str) -> None:
        if self._notifications is not None:
            await self._notifications.system(message)
