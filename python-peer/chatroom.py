import asyncio
import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import uuid
import time

logger = logging.getLogger("app")

@dataclass
class ChatMessage:
    """Represents a message in the chat."""
    message: str
    sender_id: str
    sender_nick: str
    
    def to_json(self) -> str:
        """Serialize the message to JSON format."""
        return json.dumps({
            "message": self.message,
            "sender_id": self.sender_id,
            "sender_nick": self.sender_nick
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ChatMessage':
        """Deserialize a message from JSON format."""
        try:
            data = json.loads(json_str)
            return cls(
                message=data.get("message", ""),
                sender_id=data.get("sender_id", "unknown"),
                sender_nick=data.get("sender_nick", "unknown")
            )
        except json.JSONDecodeError:
            logger.warning(f"Failed to decode message: {json_str}")
            return cls(
                message="[Invalid message format]",
                sender_id="system",
                sender_nick="system"
            )

class ChatRoom:
    """
    Represents a subscription to a chat room using libp2p PubSub.
    """
    def __init__(self, node, chat_topic: str, file_topic: str, discovery_topic: str, nickname: str):
        """
        Initialize a chat room.
        
        Args:
            node: The libp2p node
            chat_topic: The topic name for chat messages
            file_topic: The topic name for file sharing
            discovery_topic: The topic name for peer discovery
            nickname: The user's nickname
        """
        self.node = node
        self.chat_topic_name = chat_topic
        self.file_topic_name = file_topic
        self.discovery_topic_name = discovery_topic
        self.nickname = nickname
        
        # Message queues
        self.messages = asyncio.Queue(maxsize=128)
        self.sys_messages = asyncio.Queue(maxsize=128)
        
        # PubSub topics
        self.chat_topic = None
        self.file_topic = None
        self.discovery_topic = None
        
        # Subscriptions
        self.chat_subscription = None
        self.file_subscription = None
        self.discovery_subscription = None
        
        # Initialize a dictionary to store file information
        self.files = {}
        
    @classmethod
    async def join(cls, node, chat_topic: str, file_topic: str, discovery_topic: str, nickname: str) -> 'ChatRoom':
        """
        Join a chat room.
        
        Args:
            node: The libp2p node
            chat_topic: The topic name for chat messages
            file_topic: The topic name for file sharing
            discovery_topic: The topic name for peer discovery
            nickname: The user's nickname
            
        Returns:
            ChatRoom: A new chat room instance
        """
        chat_room = cls(node, chat_topic, file_topic, discovery_topic, nickname)
        
        # Get the pubsub service
        if not hasattr(node, "pubsub") or not node.pubsub:
            raise RuntimeError("PubSub service is not available on the node")
        
        # Join the chat topic
        chat_room.chat_topic = await node.pubsub.subscribe(chat_topic)
        
        # Join the file topic
        chat_room.file_topic = await node.pubsub.subscribe(file_topic)
        
        # Join the discovery topic
        chat_room.discovery_topic = await node.pubsub.subscribe(discovery_topic)
        
        # Start background tasks for processing messages
        asyncio.create_task(chat_room._handle_chat_messages())
        asyncio.create_task(chat_room._handle_file_messages())
        asyncio.create_task(chat_room._handle_discovery_messages())
        
        # Register handler for file transfer protocol
        await node.set_stream_handler("/universal-connectivity-file/1", chat_room._handle_file_request)
        
        logger.info(f"Joined chat room on topics: {chat_topic}, {file_topic}, {discovery_topic}")
        return chat_room
    
    async def _handle_chat_messages(self) -> None:
        """Process incoming chat messages."""
        while True:
            try:
                # Get the next message
                msg = await self.chat_topic.next_message()
                
                # Skip messages from ourselves
                if msg.from_peer == self.node.get_id():
                    continue
                
                # Parse the message
                try:
                    message_text = msg.data.decode('utf-8')
                    chat_message = ChatMessage(
                        message=message_text,
                        sender_id=str(msg.from_peer),
                        sender_nick=str(msg.from_peer)[-8:]  # Use last 8 chars of peer ID as nickname
                    )
                    
                    # Add to message queue
                    await self.messages.put(chat_message)
                except Exception as e:
                    logger.error(f"Error processing chat message: {e}")
            
            except asyncio.CancelledError:
                logger.info("Chat message handler task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in chat message handler: {e}")
                await asyncio.sleep(1)  # Avoid tight loop on errors
    
    async def _handle_file_messages(self) -> None:
        """Process incoming file announcement messages."""
        while True:
            try:
                # Get the next message
                msg = await self.file_topic.next_message()
                
                # Skip messages from ourselves
                if msg.from_peer == self.node.get_id():
                    continue
                
                # The message should contain a file ID
                file_id = msg.data.decode('utf-8')
                
                # Request the file from the sender
                try:
                    file_data = await self._request_file(msg.from_peer, file_id)
                    
                    # Store the file
                    self.files[file_id] = {
                        "data": file_data,
                        "from_peer": str(msg.from_peer),
                        "timestamp": time.time()
                    }
                    
                    # Notify about the file
                    await self.messages.put(ChatMessage(
                        message=f"File: {file_id} ({len(file_data)} bytes) from {str(msg.from_peer)}",
                        sender_id=str(msg.from_peer),
                        sender_nick=str(msg.from_peer)[-8:]
                    ))
                
                except Exception as e:
                    logger.error(f"Error requesting file {file_id} from {msg.from_peer}: {e}")
            
            except asyncio.CancelledError:
                logger.info("File message handler task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in file message handler: {e}")
                await asyncio.sleep(1)  # Avoid tight loop on errors
    
    async def _handle_discovery_messages(self) -> None:
        """Process incoming peer discovery messages."""
        while True:
            try:
                # Get the next message
                msg = await self.discovery_topic.next_message()
                
                # Skip messages from ourselves
                if msg.from_peer == self.node.get_id():
                    continue
                
                # The message should contain peer information
                try:
                    peer_info = json.loads(msg.data.decode('utf-8'))
                    peer_id = peer_info.get("peer_id")
                    addrs = peer_info.get("addrs", [])
                    
                    if peer_id and addrs:
                        logger.info(f"Discovered peer {peer_id} with addresses: {addrs}")
                        
                        # Try to connect if not already connected
                        if not self.node.is_connected(peer_id):
                            for addr in addrs:
                                try:
                                    await self.node.connect(f"{addr}/p2p/{peer_id}")
                                    logger.info(f"Connected to discovered peer {peer_id}")
                                    break
                                except Exception as e:
                                    logger.warning(f"Failed to connect to {peer_id} at {addr}: {e}")
                except Exception as e:
                    logger.error(f"Error processing discovery message: {e}")
            
            except asyncio.CancelledError:
                logger.info("Discovery message handler task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in discovery message handler: {e}")
                await asyncio.sleep(1)  # Avoid tight loop on errors
    
    async def _handle_file_request(self, stream) -> None:
        """Handle incoming file requests."""
        try:
            # Read the request (length-prefixed file ID)
            length_bytes = await stream.read(8)  # Read up to 8 bytes for the length prefix
            length = int.from_bytes(length_bytes, byteorder='big')
            
            if length > 1000000:  # Limit to 1MB file IDs
                logger.warning(f"File ID too large: {length} bytes")
                await stream.reset()
                return
            
            file_id = await stream.read(length)
            file_id_str = file_id.decode('utf-8')
            
            # Check if we have this file
            if file_id_str in self.files:
                file_data = self.files[file_id_str]["data"]
                
                # Send the file (length-prefixed)
                await stream.write(len(file_data).to_bytes(8, byteorder='big'))
                await stream.write(file_data)
                logger.info(f"Sent file {file_id_str} ({len(file_data)} bytes)")
            else:
                # File not found - send empty response
                await stream.write((0).to_bytes(8, byteorder='big'))
                logger.warning(f"Requested file {file_id_str} not found")
            
            # Close the stream
            await stream.close()
        
        except Exception as e:
            logger.error(f"Error handling file request: {e}")
            try:
                await stream.reset()
            except:
                pass
    
    async def _request_file(self, peer_id, file_id: str) -> bytes:
        """
        Request a file from a peer.
        
        Args:
            peer_id: The peer to request the file from
            file_id: The ID of the file to request
            
        Returns:
            bytes: The file data
        """
        # Create a new stream to the peer
        stream = await self.node.new_stream(peer_id, ["/universal-connectivity-file/1"])
        
        try:
            # Send the request (length-prefixed file ID)
            file_id_bytes = file_id.encode('utf-8')
            await stream.write(len(file_id_bytes).to_bytes(8, byteorder='big'))
            await stream.write(file_id_bytes)
            
            # Read the response (length-prefixed file data)
            length_bytes = await stream.read(8)
            length = int.from_bytes(length_bytes, byteorder='big')
            
            if length == 0:
                raise ValueError(f"File {file_id} not found on peer {peer_id}")
            
            if length > 500_000_000:  # Limit to 500MB files
                raise ValueError(f"File too large: {length} bytes")
            
            # Read the file data
            file_data = await stream.read(length)
            
            # Close the stream
            await stream.close()
            
            return file_data
        
        except Exception as e:
            logger.error(f"Error requesting file: {e}")
            try:
                await stream.reset()
            except:
                pass
            raise
    
    async def publish(self, message: str) -> None:
        """
        Publish a message to the chat topic.
        
        Args:
            message: The message to publish
        """
        if not message:
            return
        
        try:
            # Create a chat message
            chat_message = ChatMessage(
                message=message,
                sender_id=str(self.node.get_id()),
                sender_nick=self.nickname
            )
            
            # Publish the message
            await self.chat_topic.publish(message.encode('utf-8'))
            logger.debug(f"Published message: {message}")
        
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            # Add error message to system messages
            await self.sys_messages.put(ChatMessage(
                message=f"Failed to send message: {e}",
                sender_id="system",
                sender_nick="system"
            ))
    
    async def share_file(self, file_data: bytes, file_name: Optional[str] = None) -> str:
        """
        Share a file with the chat room.
        
        Args:
            file_data: The file data to share
            file_name: Optional file name
            
        Returns:
            str: The file ID used to reference the file
        """
        # Generate a file ID
        file_id = file_name or f"file-{uuid.uuid4()}"
        
        # Store the file
        self.files[file_id] = {
            "data": file_data,
            "from_peer": str(self.node.get_id()),
            "timestamp": time.time()
        }
        
        try:
            # Announce the file
            await self.file_topic.publish(file_id.encode('utf-8'))
            
            # Notify about the file locally
            await self.sys_messages.put(ChatMessage(
                message=f"Shared file: {file_id} ({len(file_data)} bytes)",
                sender_id="system",
                sender_nick="system"
            ))
            
            return file_id
        
        except Exception as e:
            logger.error(f"Error sharing file: {e}")
            # Add error message to system messages
            await self.sys_messages.put(ChatMessage(
                message=f"Failed to share file: {e}",
                sender_id="system",
                sender_nick="system"
            ))
            raise
    
    def list_peers(self) -> List[str]:
        """
        List peers subscribed to the chat topic.
        
        Returns:
            List[str]: List of peer IDs
        """
        try:
            return self.node.pubsub.get_peers(self.chat_topic_name)
        except Exception as e:
            logger.error(f"Error listing peers: {e}")
            return []