import React, { useEffect, useState } from 'react'
import { Text, Frame, View } from 'react-curse'
import { useLibp2pContext } from '../context/index.js'
import { PUBLIC_CHAT_ROOM_ID } from '../constants.js'
import { ChatMessage, useChatContext } from '../context/chat.js'
import { Message } from './message.js'
import { Logger } from '@libp2p/interface'
import { layout, PositionProps } from '../index.js'
import { shortPeerId } from '../lib/short-peer-id.js'

let log: Logger

export default function Messages(props: PositionProps) {
  const { libp2p } = useLibp2pContext()
  const { roomId, setRoomId } = useChatContext()
  const { messageHistory, setMessageHistory, directMessages, setDirectMessages } = useChatContext()
  const [ messages, setMessages ] = useState<ChatMessage[]>([])

  log = log ?? libp2p.logger.forComponent('chat')

  const handleBackToPublic = () => {
    setRoomId(PUBLIC_CHAT_ROOM_ID)
    setMessages(messageHistory)
  }

  useEffect(() => {
    // assumes a chat room is a peerId thus a direct message
    if (roomId === PUBLIC_CHAT_ROOM_ID) {
      setMessages(messageHistory)
    } else {
      setMessages(directMessages[roomId] || [])
    }
  }, [roomId, directMessages, messageHistory])

  const title = roomId === PUBLIC_CHAT_ROOM_ID ? `Public chat (${shortPeerId(libp2p.peerId)})` : `DM (${shortPeerId(libp2p.peerId)} x ${shortPeerId(roomId)})`

  return (
    <>
      <Frame absolute={true} {...props}>
        <View>{
          messages.map(({ msgId, msg, peerId, read, receivedAt }) => (
            <Message
              key={msgId}
              dm={roomId !== PUBLIC_CHAT_ROOM_ID}
              msg={msg}
              peerId={peerId}
              read={read}
              msgId={msgId}
              receivedAt={receivedAt}
              children={[]}
            />
          ))
        }</View>
      </Frame>
      <Text absolute={true} x={props.x + layout.margin} y={props.y}>{title}</Text>
    </>
  )
}
