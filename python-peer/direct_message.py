import asyncio
import json
import logging
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable, List

logger = logging.getLogger("app")

# Protocol definitions
DIRECT_MESSAGE_PROTOCOL = "/universal-connectivity/direct-message/1.0.0"
MIME_TEXT_PLAIN = "text/plain"
DM_CLIENT_VERSION = "0.0.1"

class Status(Enum):
    UNKNOWN = 0
    OK = 200
    ERROR = 500

class DirectMessageService:
    """
    Implementation of the direct messaging protocol.
    
    This service allows sending direct messages to specific peers
    rather than broadcasting to the entire pubsub topic.
    """
    def __init__(self, node):
        """
        Initialize the direct messaging service.
        
        Args:
            node: The libp2p node
        """
        self.node = node
        self.dm_peers = set()  # Set of peers supporting direct messaging
        self.message_handlers = []  # List of message handler callbacks
    
    async def start(self) -> None:
        """Start the direct messaging service."""
        # Register the direct message protocol handler
        await self.node.set_stream_handler(DIRECT_MESSAGE_PROTOCOL, self._handle_direct_message)
        logger.info(f"Registered direct message protocol handler: {DIRECT_MESSAGE_PROTOCOL}")
    
    async def stop(self) -> None:
        """Stop the direct messaging service."""
        # Remove the protocol handler
        await self.node.remove_stream_handler(DIRECT_MESSAGE_PROTOCOL)
        logger.info("Removed direct message protocol handler")
    
    def add_message_handler(self, handler: Callable) -> None:
        """
        Add a handler for incoming direct messages.
        
        Args:
            handler: Callback function that takes (from_peer, content, type)
        """
        self.message_handlers.append(handler)
    
    def remove_message_handler(self, handler: Callable) -> None:
        """
        Remove a message handler.
        
        Args:
            handler: The handler to remove
        """
        if handler in self.message_handlers:
            self.message_handlers.remove(handler)
    
    def handle_peer_connected(self, peer_id: str) -> None:
        """
        Handle a peer connection event.
        
        Args:
            peer_id: The connected peer ID
        """
        self.dm_peers.add(peer_id)
    
    def handle_peer_disconnected(self, peer_id: str) -> None:
        """
        Handle a peer disconnection event.
        
        Args:
            peer_id: The disconnected peer ID
        """
        if peer_id in self.dm_peers:
            self.dm_peers.remove(peer_id)
    
    def is_dm_peer(self, peer_id: str) -> bool:
        """
        Check if a peer supports direct messaging.
        
        Args:
            peer_id: The peer ID to check
            
        Returns:
            bool: True if the peer supports direct messaging
        """
        return peer_id in self.dm_peers
    
    async def send_message(self, peer_id: str, content: str, msg_type: str = MIME_TEXT_PLAIN) -> bool:
        """
        Send a direct message to a peer.
        
        Args:
            peer_id: The peer ID to send the message to
            content: The message content
            msg_type: The message type/MIME type
            
        Returns:
            bool: True if the message was sent successfully
        """
        if not content:
            logger.error("Message content cannot be empty")
            return False
        
        # Create a stream to the peer
        try:
            stream = await self.node.new_stream(peer_id, [DIRECT_MESSAGE_PROTOCOL])
        except Exception as e:
            logger.error(f"Failed to create stream to peer {peer_id}: {e}")
            return False
        
        try:
            # Prepare the request
            request = {
                "content": content,
                "type": msg_type,
                "metadata": {
                    "client_version": DM_CLIENT_VERSION,
                    "timestamp": int(time.time() * 1000)  # milliseconds
                }
            }
            
            # Send the request
            request_json = json.dumps(request).encode('utf-8')
            length_prefix = len(request_json).to_bytes(4, byteorder='big')
            await stream.write(length_prefix + request_json)
            
            # Read the response
            response_length_bytes = await stream.read(4)
            if not response_length_bytes:
                logger.error("No response received")
                return False
            
            response_length = int.from_bytes(response_length_bytes, byteorder='big')
            response_json = await stream.read(response_length)
            
            # Parse the response
            response = json.loads(response_json.decode('utf-8'))
            
            if not response.get("metadata"):
                logger.error("No metadata in response")
                return False
            
            if response.get("status") != Status.OK.value:
                logger.error(f"Received error status: {response.get('status')}")
                return False
            
            # Add to DM peers set if successful
            self.dm_peers.add(peer_id)
            
            return True
        
        except Exception as e:
            logger.error(f"Error sending direct message: {e}")
            return False
        
        finally:
            # Close the stream
            try:
                await stream.close()
            except Exception as e:
                logger.error(f"Error closing stream: {e}")
    
    async def _handle_direct_message(self, stream) -> None:
        """
        Handle incoming direct messages.
        
        Args:
            stream: The incoming stream
        """
        try:
            # Read the request length
            length_bytes = await stream.read(4)
            if not length_bytes:
                logger.error("Empty message received")
                await stream.reset()
                return
            
            request_length = int.from_bytes(length_bytes, byteorder='big')
            if request_length > 1000000:  # Limit to 1MB messages
                logger.warning(f"Message too large: {request_length} bytes")
                await stream.reset()
                return
            
            # Read the request body
            request_json = await stream.read(request_length)
            request = json.loads(request_json.decode('utf-8'))
            
            # Prepare the response
            response = {
                "status": Status.OK.value,
                "metadata": {
                    "client_version": DM_CLIENT_VERSION,
                    "timestamp": int(time.time() * 1000)
                }
            }
            
            # Send the response
            response_json = json.dumps(response).encode('utf-8')
            length_prefix = len(response_json).to_bytes(4, byteorder='big')
            await stream.write(length_prefix + response_json)
            
            # Close the stream
            await stream.close()
            
            # Add the sender to the DM peers set
            peer_id = stream.conn.remote_peer_id
            self.dm_peers.add(peer_id)
            
            # Notify message handlers
            content = request.get("content", "")
            msg_type = request.get("type", MIME_TEXT_PLAIN)
            
            for handler in self.message_handlers:
                try:
                    await handler(peer_id, content, msg_type)
                except Exception as e:
                    logger.error(f"Error in message handler: {e}")
        
        except Exception as e:
            logger.error(f"Error handling direct message: {e}")
            try:
                await stream.reset()
            except:
                pass