import React, { createContext, useContext, useEffect, useState } from 'react'
import { useLibp2pContext } from './index.js'
import type { Logger, Message } from '@libp2p/interface'
import {
  CHAT_TOPIC,
  MIME_TEXT_PLAIN,
  PUBSUB_PEER_DISCOVERY,
} from '../constants.js'
import { DirectMessageEvent, directMessageEvent } from '../lib/direct-message.js'

let log: Logger

export interface ChatMessage {
  msgId: string
  msg: string
  peerId: string
  read: boolean
  receivedAt: number
}

export interface DirectMessages {
  [peerId: string]: ChatMessage[]
}

type Chatroom = string

export interface ChatContextInterface {
  messageHistory: ChatMessage[]
  setMessageHistory: (messageHistory: ChatMessage[] | ((prevMessages: ChatMessage[]) => ChatMessage[])) => void
  directMessages: DirectMessages
  setDirectMessages: (directMessages: DirectMessages | ((prevMessages: DirectMessages) => DirectMessages)) => void
  roomId: Chatroom
  setRoomId: (chatRoom: Chatroom) => void
}

export const chatContext = createContext<ChatContextInterface>({
  messageHistory: [],
  setMessageHistory: () => {},
  directMessages: {},
  setDirectMessages: () => {},
  roomId: '',
  setRoomId: () => {}
})

export const useChatContext = () => {
  return useContext(chatContext)
}

export const ChatProvider = ({ children }: any) => {
  const [messageHistory, setMessageHistory] = useState<ChatMessage[]>([])
  const [directMessages, setDirectMessages] = useState<DirectMessages>({})
  const [roomId, setRoomId] = useState<Chatroom>('')

  const { libp2p } = useLibp2pContext()
  log = log ?? libp2p.logger.forComponent('chat-context')

  const messageCB = (evt: CustomEvent<Message>) => {
    const { topic, data } = evt.detail

    switch (topic) {
      case CHAT_TOPIC: {
        chatMessageCB(evt, topic, data)
        break
      }
      case PUBSUB_PEER_DISCOVERY: {
        break
      }
      default: {
        log.error('Unexpected event %o on gossipsub topic: %s', evt, topic)
      }
    }
  }

  const chatMessageCB = (evt: CustomEvent<Message>, topic: string, data: Uint8Array) => {
    const msg = new TextDecoder().decode(data)
    log(`${topic}: ${msg}`)

    // Append signed messages, otherwise discard
    if (evt.detail.type === 'signed') {
      setMessageHistory([
        ...messageHistory,
        {
          msgId: crypto.randomUUID(),
          msg,
          peerId: evt.detail.from.toString(),
          read: false,
          receivedAt: Date.now(),
        },
      ])
    }
  }

  useEffect(() => {
    const handleDirectMessage = (evt: CustomEvent<DirectMessageEvent>) => {
      const peerId = evt.detail.connection.remotePeer.toString()

      if (evt.detail.type !== MIME_TEXT_PLAIN) {
        throw new Error(`unexpected message type: ${evt.detail.type}`)
      }

      const message: ChatMessage = {
        msg: evt.detail.content,
        read: false,
        msgId: crypto.randomUUID(),
        peerId: peerId,
        receivedAt: Date.now(),
      }

      const updatedMessages = directMessages[peerId] ? [...directMessages[peerId], message] : [message]

      setDirectMessages({
        ...directMessages,
        [peerId]: updatedMessages,
      })
    }

    libp2p.services.directMessage.addEventListener(directMessageEvent, handleDirectMessage)

    return () => {
      libp2p.services.directMessage.removeEventListener(directMessageEvent, handleDirectMessage)
    }
  }, [directMessages, libp2p.services.directMessage, setDirectMessages])

  useEffect(() => {
    libp2p.services.pubsub.addEventListener('message', messageCB)

    return () => {
      ;(async () => {
        // Cleanup handlers 👇
        libp2p.services.pubsub.removeEventListener('message', messageCB)
      })()
    }
  })

  return (
    <chatContext.Provider
      value={{
        roomId,
        setRoomId,
        messageHistory,
        setMessageHistory,
        directMessages,
        setDirectMessages
      }}
    >
      {children}
    </chatContext.Provider>
  )
}
