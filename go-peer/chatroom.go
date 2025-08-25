package main

import (
	"bufio"
	"context"
	"encoding/binary"
	"fmt"

	"github.com/ipfs/go-log/v2"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/peer"

	pubsub "github.com/libp2p/go-libp2p-pubsub"
)

var chatLogger = log.Logger("chatroom")

// ChatRoomBufSize is the number of incoming messages to buffer for each topic.
const ChatRoomBufSize = 128

// Topic used to broadcast browser WebRTC addresses
const PubSubDiscoveryTopic string = "universal-connectivity-browser-peer-discovery"

const ChatTopic string = "universal-connectivity"
const ChatFileTopic string = "universal-connectivity-file"

// ChatRoom represents a subscription to a single PubSub topic. Messages
// can be published to the topic with ChatRoom.Publish, and received
// messages are pushed to the Messages channel.
type ChatRoom struct {
	// Messages is a channel of messages received from other peers in the chat room
	Messages    chan *ChatMessage
	SysMessages chan *ChatMessage

	ctx                context.Context
	h                  host.Host
	ps                 *pubsub.PubSub
	chatTopic          *pubsub.Topic
	chatSub            *pubsub.Subscription
	fileTopic          *pubsub.Topic
	fileSub            *pubsub.Subscription
	peerDiscoveryTopic *pubsub.Topic
	peerDiscoverySub   *pubsub.Subscription

	roomName string
	nick     string
}

// ChatMessage gets converted to/from JSON and sent in the body of pubsub messages.
type ChatMessage struct {
	Message    string
	SenderID   string
	SenderNick string
}

// JoinChatRoom tries to subscribe to the PubSub topic for the room name, returning
// a ChatRoom on success.
func JoinChatRoom(ctx context.Context, h host.Host, ps *pubsub.PubSub, nickname string) (*ChatRoom, error) {
	chatLogger.Infof("📡 Joining chat room with nickname: %s", nickname)
	
	// join the pubsub chatTopic
	chatLogger.Infof("📡 Joining chat topic: %s", ChatTopic)
	chatTopic, err := ps.Join(ChatTopic)
	if err != nil {
		chatLogger.Errorf("❌ Failed to join chat topic: %v", err)
		return nil, err
	}
	chatLogger.Infof("✅ Successfully joined chat topic: %s", ChatTopic)

	// and subscribe to it
	chatLogger.Infof("📡 Subscribing to chat topic...")
	chatSub, err := chatTopic.Subscribe()
	if err != nil {
		chatLogger.Errorf("❌ Failed to subscribe to chat topic: %v", err)
		return nil, err
	}
	chatLogger.Infof("✅ Successfully subscribed to chat topic")

	// join the pubsub fileTopic
	chatLogger.Infof("📡 Joining file topic: %s", ChatFileTopic)
	fileTopic, err := ps.Join(ChatFileTopic)
	if err != nil {
		chatLogger.Errorf("❌ Failed to join file topic: %v", err)
		return nil, err
	}
	chatLogger.Infof("✅ Successfully joined file topic: %s", ChatFileTopic)

	// and subscribe to it
	chatLogger.Infof("📡 Subscribing to file topic...")
	fileSub, err := fileTopic.Subscribe()
	if err != nil {
		chatLogger.Errorf("❌ Failed to subscribe to file topic: %v", err)
		return nil, err
	}
	chatLogger.Infof("✅ Successfully subscribed to file topic")

	// join the pubsub peer disovery topic
	chatLogger.Infof("📡 Joining peer discovery topic: %s", PubSubDiscoveryTopic)
	peerDiscoveryTopic, err := ps.Join(PubSubDiscoveryTopic)
	if err != nil {
		chatLogger.Errorf("❌ Failed to join peer discovery topic: %v", err)
		return nil, err
	}
	chatLogger.Infof("✅ Successfully joined peer discovery topic: %s", PubSubDiscoveryTopic)

	// and subscribe to it
	chatLogger.Infof("📡 Subscribing to peer discovery topic...")
	peerDiscoverySub, err := peerDiscoveryTopic.Subscribe()
	if err != nil {
		chatLogger.Errorf("❌ Failed to subscribe to peer discovery topic: %v", err)
		return nil, err
	}
	chatLogger.Infof("✅ Successfully subscribed to peer discovery topic")

	chatLogger.Infof("✅ Successfully subscribed to peer discovery topic")

	cr := &ChatRoom{
		ctx:                ctx,
		h:                  h,
		ps:                 ps,
		chatTopic:          chatTopic,
		chatSub:            chatSub,
		fileTopic:          fileTopic,
		fileSub:            fileSub,
		peerDiscoveryTopic: peerDiscoveryTopic,
		peerDiscoverySub:   peerDiscoverySub,
		nick:               nickname,
		Messages:           make(chan *ChatMessage, ChatRoomBufSize),
		SysMessages:        make(chan *ChatMessage, ChatRoomBufSize),
	}

	chatLogger.Infof("📡 Starting message read loops...")
	// start reading messages from the subscription in a loop
	go cr.readLoop()
	
	chatLogger.Infof("✅ ChatRoom initialization complete for nickname: %s", nickname)
	return cr, nil
}

// Publish sends a message to the pubsub topic.
func (cr *ChatRoom) Publish(message string) error {
	chatLogger.Infof("📤 Publishing message to chat topic: %s", message)
	peers := cr.ps.ListPeers(ChatTopic)
	chatLogger.Infof("📡 Publishing to %d peers on topic '%s'", len(peers), ChatTopic)
	for i, peerID := range peers {
		chatLogger.Infof("  📡 Peer %d: %s", i+1, peerID)
	}
	
	err := cr.chatTopic.Publish(cr.ctx, []byte(message))
	if err != nil {
		chatLogger.Errorf("❌ Failed to publish message: %v", err)
		return err
	}
	chatLogger.Infof("✅ Message published successfully")
	return nil
}

func (cr *ChatRoom) ListPeers() []peer.ID {
	peers := cr.ps.ListPeers(ChatTopic)
	chatLogger.Infof("📡 Current peers on topic '%s': %d", ChatTopic, len(peers))
	for i, peerID := range peers {
		chatLogger.Infof("  📡 Peer %d: %s", i+1, peerID)
	}
	return peers
}

// readLoop pulls messages from the pubsub chat/file topic and handles them.
func (cr *ChatRoom) readLoop() {
	chatLogger.Infof("📡 Starting chat message read loop...")
	go cr.readChatLoop()
	chatLogger.Infof("📡 Starting file message read loop...")
	go cr.readFileLoop()
}

// readChatLoop pulls messages from the pubsub chat topic and pushes them onto the Messages channel.
func (cr *ChatRoom) readChatLoop() {
	chatLogger.Infof("📡 Chat message read loop started")
	for {
		chatLogger.Debugf("📡 Waiting for next chat message...")
		msg, err := cr.chatSub.Next(cr.ctx)
		if err != nil {
			chatLogger.Errorf("❌ Error reading chat message: %v", err)
			close(cr.Messages)
			return
		}
		
		chatLogger.Infof("📨 Received chat message from peer %s", msg.ReceivedFrom)
		chatLogger.Infof("📨 Message content: %s", string(msg.Data))
		chatLogger.Infof("📨 Message ID: %s", msg.ID)
		
		// only forward messages delivered by others
		if msg.ReceivedFrom == cr.h.ID() {
			chatLogger.Infof("📨 Ignoring own message")
			continue
		}
		
		cm := new(ChatMessage)
		cm.Message = string(msg.Data)
		cm.SenderID = string(msg.ReceivedFrom)
		cm.SenderNick = shortID(msg.ReceivedFrom)  // Use the shortID function for consistency
		
		chatLogger.Infof("📨 Forwarding message to UI: sender=%s, content=%s", cm.SenderNick, cm.Message)
		// send valid messages onto the Messages channel
		cr.Messages <- cm
	}
}

// readFileLoop pulls messages from the pubsub file topic and handles them.
func (cr *ChatRoom) readFileLoop() {
	for {
		msg, err := cr.fileSub.Next(cr.ctx)
		if err != nil {
			close(cr.Messages)
			return
		}
		// only forward messages delivered by others
		if msg.ReceivedFrom == cr.h.ID() {
			continue
		}

		fileID := msg.Data
		fileBody, err := cr.requestFile(msg.GetFrom(), fileID)
		if err != nil {
			close(cr.Messages)
			return
		}

		cm := new(ChatMessage)
		cm.Message = fmt.Sprintf("File: %s (%v bytes) from %s", string(fileID), len(fileBody), msg.GetFrom().String())
		cm.SenderID = msg.ID
		cm.SenderNick = string(msg.ID[len(msg.ID)-8])
		// send valid messages onto the Messages channel
		cr.Messages <- cm
	}
}

// requestFile sends a request to the peer to send the file with the given fileID.
func (cr *ChatRoom) requestFile(toPeer peer.ID, fileID []byte) ([]byte, error) {
	stream, err := cr.h.NewStream(context.Background(), toPeer, "/universal-connectivity-file/1")
	if err != nil {
		return nil, fmt.Errorf("failed to create stream: %w", err)
	}
	defer stream.Close()

	reqLen := binary.AppendUvarint([]byte{}, uint64(len(fileID)))
	if _, err := stream.Write(reqLen); err != nil {
		return nil, fmt.Errorf("failed to write fileID to the stream: %w", err)
	}
	if _, err := stream.Write(fileID); err != nil {
		return nil, fmt.Errorf("failed to write fileID to the stream: %w", err)
	}
	if err := stream.CloseWrite(); err != nil {
		return nil, fmt.Errorf("failed to close write stream: %w", err)
	}

	reader := bufio.NewReader(stream)
	respLen, err := binary.ReadUvarint(reader)
	if err != nil {
		return nil, fmt.Errorf("failed to read response length prefix: %w", err)
	}
	fileBody := make([]byte, respLen)
	if _, err := reader.Read(fileBody); err != nil {
		return nil, fmt.Errorf("failed to read fileBody from the stream: %w", err)
	}
	if err := stream.CloseRead(); err != nil {
		return nil, fmt.Errorf("failed to close read stream: %w", err)
	}

	return fileBody, nil
}
