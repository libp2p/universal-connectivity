"""
Message handlers for pubsub operations.
"""
import base58
import trio
from typing import Any, Set, Callable, Awaitable
from libp2p.pubsub.pubsub import ISubscriptionAPI

from libp2p.pubsub.pubsub import Pubsub
from py_peer.utils.logging import get_logger

logger = get_logger(__name__)


async def receive_loop(subscription: ISubscriptionAPI) -> None:
    """
    Loop to receive messages from a subscription.
    
    Args:
        subscription: The subscription to receive messages from
    """
    logger.debug("Starting receive loop")
    while True:
        try:
            message = await subscription.get()
            logger.info(f"From peer: {base58.b58encode(message.from_id).decode()}")
            print(f"Received message: {message.data.decode('utf-8')}")
        except Exception:
            logger.exception("Error in receive loop")
            await trio.sleep(1)


async def publish_loop(pubsub: Pubsub, topic: str) -> None:
    """
    Loop to publish messages to a topic.
    
    Args:
        pubsub: The pubsub instance
        topic: The topic to publish to
    """
    logger.debug("Starting publish loop...")
    print("Type messages to send (press Enter to send, 'quit' to exit):")
    while True:
        try:
            # Use trio's run_sync_in_worker_thread to avoid blocking the event loop
            message = await trio.to_thread.run_sync(input)
            if message.lower() == "quit":
                print("Exiting publish loop.")
                break
            if message:
                logger.debug(f"Publishing message: {message}")
                await pubsub.publish(topic, message.encode())
                print(f"Published: {message}")
        except Exception:
            logger.exception("Error in publish loop")
            await trio.sleep(1)  # Avoid tight loop on error

async def monitor_peer_topics(
    pubsub: Pubsub, 
    on_new_topic: Callable[[str, Any], Awaitable[None]]
) -> None:
    """
    Monitor for new topics that peers are subscribed to.
    
    Args:
        pubsub: The pubsub instance
        on_new_topic: Callback function for new topics
    """
    # Keep track of topics we've already subscribed to
    subscribed_topics: Set[str] = set()

    while True:
        # Check for new topics in peer_topics
        for topic in pubsub.peer_topics.keys():
            if topic not in subscribed_topics:
                logger.info(f"Auto-subscribing to new topic: {topic}")
                subscription = await pubsub.subscribe(topic)
                subscribed_topics.add(topic)
                # Call the callback for the new topic
                await on_new_topic(topic, subscription)

        # Check every 2 seconds for new topics
        await trio.sleep(2)