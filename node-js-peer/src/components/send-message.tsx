import React, { useCallback } from 'react'
import { Text, Frame, Input } from 'react-curse'
import { useLibp2pContext } from '../context/index.js'
import { CHAT_TOPIC, PUBLIC_CHAT_ROOM_ID } from '../constants.js'
import { layout, PositionProps } from '../lib/position.js'
import { ChatMessage, useChatContext } from '../context/chat.js'
import { peerIdFromString } from '@libp2p/peer-id'
import { Logger } from '@libp2p/interface'

let log: Logger

export function SendMessage(props: PositionProps) {
  const { libp2p } = useLibp2pContext()
  const { roomId, messageHistory, setMessageHistory, directMessages, setDirectMessages } = useChatContext()

  log ??= libp2p.logger.forComponent('chat:send-message')

  const onSubmit = (text) => {
    if (roomId === PUBLIC_CHAT_ROOM_ID) {
      sendPublicMessage(text)
    } else {
      sendDirectMessage(text)
    }
  }

  // Send message to public chat over gossipsub
  const sendPublicMessage = useCallback(async (input: string) => {
    if (input === '') {
      return
    }

    await libp2p.services.pubsub.publish(CHAT_TOPIC, new TextEncoder().encode(input))
    const myPeerId = libp2p.peerId.toString()

    setMessageHistory([
      ...messageHistory,
      {
        msgId: crypto.randomUUID(),
        msg: input,
        peerId: myPeerId,
        read: true,
        receivedAt: Date.now(),
      },
    ])
  }, [messageHistory, libp2p, setMessageHistory])

  // Send direct message over custom protocol
  const sendDirectMessage = useCallback(async (input: string) => {
    try {
      const res = await libp2p.services.directMessage.send(peerIdFromString(roomId), input)

      if (!res) {
        log('Failed to send message')
        return
      }

      const myPeerId = libp2p.peerId.toString()

      const newMessage: ChatMessage = {
        msgId: crypto.randomUUID(),
        msg: input,
        peerId: myPeerId,
        read: true,
        receivedAt: Date.now(),
      }

      const updatedMessages = directMessages[roomId] ? [...directMessages[roomId], newMessage] : [newMessage]

      setDirectMessages({
        ...directMessages,
        [roomId]: updatedMessages,
      })
    } catch (e: any) {
      log.error('error sending message - %e', e)
    }
  }, [libp2p, setDirectMessages, directMessages, roomId])

  return (
    <>
      <Frame absolute={true} {...props}>
        <Input onSubmit={onSubmit}></Input>
      </Frame>
      <Text absolute={true} x={props.x + layout.margin} y={props.y}>Send message</Text>
    </>
  )
}
