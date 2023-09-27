package main

import (
	"bufio"
	"context"
	"encoding/binary"
	"fmt"

	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/peer"

	pubsub "github.com/libp2p/go-libp2p-pubsub"
)

// ChatRoomBufSize is the number of incoming messages to buffer for each topic.
const ChatRoomBufSize = 128

// ChatRoom represents a subscription to a single PubSub topic. Messages
// can be published to the topic with ChatRoom.Publish, and received
// messages are pushed to the Messages channel.
type ChatRoom struct {
	// Messages is a channel of messages received from other peers in the chat room
	Messages    chan *ChatMessage
	SysMessages chan *ChatMessage

	ctx       context.Context
	h         host.Host
	ps        *pubsub.PubSub
	chatTopic *pubsub.Topic
	chatSub   *pubsub.Subscription
	fileTopic *pubsub.Topic
	fileSub   *pubsub.Subscription

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
func JoinChatRoom(ctx context.Context, h host.Host, ps *pubsub.PubSub, nickname string, roomName string) (*ChatRoom, error) {
	// join the pubsub chatTopic
	chatTopic, err := ps.Join(chatTopicName(roomName))
	if err != nil {
		return nil, err
	}

	// and subscribe to it
	chatSub, err := chatTopic.Subscribe()
	if err != nil {
		return nil, err
	}

	// join the pubsub fileTopic
	fileTopic, err := ps.Join(fileTopicName(roomName))
	if err != nil {
		return nil, err
	}

	// and subscribe to it
	fileSub, err := fileTopic.Subscribe()
	if err != nil {
		return nil, err
	}

	cr := &ChatRoom{
		ctx:         ctx,
		h:           h,
		ps:          ps,
		chatTopic:   chatTopic,
		chatSub:     chatSub,
		fileTopic:   fileTopic,
		fileSub:     fileSub,
		nick:        nickname,
		roomName:    roomName,
		Messages:    make(chan *ChatMessage, ChatRoomBufSize),
		SysMessages: make(chan *ChatMessage, ChatRoomBufSize),
	}

	// start reading messages from the subscription in a loop
	go cr.readLoop()
	return cr, nil
}

// Publish sends a message to the pubsub topic.
func (cr *ChatRoom) Publish(message string) error {
	return cr.chatTopic.Publish(cr.ctx, []byte(message))
}

func (cr *ChatRoom) ListPeers() []peer.ID {
	return cr.ps.ListPeers(chatTopicName(cr.roomName))
}

// readLoop pulls messages from the pubsub chat/file topic and handles them.
func (cr *ChatRoom) readLoop() {
	go cr.readChatLoop()
	go cr.readFileLoop()
}

// readChatLoop pulls messages from the pubsub chat topic and pushes them onto the Messages channel.
func (cr *ChatRoom) readChatLoop() {
	for {
		msg, err := cr.chatSub.Next(cr.ctx)
		if err != nil {
			close(cr.Messages)
			return
		}
		// only forward messages delivered by others
		if msg.ReceivedFrom == cr.h.ID() {
			continue
		}
		cm := new(ChatMessage)
		cm.Message = string(msg.Data)
		cm.SenderID = msg.ID
		cm.SenderNick = string(msg.ID[len(msg.ID)-8])
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

// chatTopicName returns the name of the pubsub topic for the chat room.
func chatTopicName(roomName string) string {
	return roomName
}

// fileTopicName returns the name of the pubsub topic used for sending/recieving files in the chat room.
func fileTopicName(roomName string) string {
	return fmt.Sprintf("%s-file", roomName)
}
