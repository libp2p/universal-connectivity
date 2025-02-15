import React, { createContext, useContext, useEffect, useState } from 'react'
import { useLibp2pContext } from './ctx'
import type { Message, PeerId } from '@libp2p/interface'
import { peerIdFromString } from '@libp2p/peer-id'
import {
  CHAT_FILE_TOPIC,
  CHAT_TOPIC,
  FILE_EXCHANGE_PROTOCOL,
  MIME_TEXT_PLAIN,
  PUBSUB_PEER_DISCOVERY,
} from '@/lib/constants'
import { toString as uint8ArrayToString } from 'uint8arrays/to-string'
import { fromString as uint8ArrayFromString } from 'uint8arrays/from-string'
import { pipe } from 'it-pipe'
import map from 'it-map'
import * as lp from 'it-length-prefixed'
import { forComponent } from '@/lib/logger'
import { messageStore } from '@/lib/message-store'
import { DirectMessageEvent, directMessageEvent } from '@/lib/direct-message'

const log = forComponent('chat-context')

export interface ChatMessage {
  msgId: string
  msg: string
  fileObjectUrl: string | undefined
  peerId: string
  read: boolean
  receivedAt: number
}

export interface ChatFile {
  id: string
  body: Uint8Array
  sender: string
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
  files: Map<string, ChatFile>
  setFiles: (files: Map<string, ChatFile>) => void
  activeVideoCall: string | null
  setActiveVideoCall: (peerId: string | null) => void
  initiateVideoCall: (peerId: string) => Promise<void>
}

export const chatContext = createContext<ChatContextInterface>({
  messageHistory: [],
  setMessageHistory: () => {},
  directMessages: {},
  setDirectMessages: () => {},
  roomId: '',
  setRoomId: () => {},
  files: new Map<string, ChatFile>(),
  setFiles: () => {},
  activeVideoCall: null,
  setActiveVideoCall: () => {},
  initiateVideoCall: async () => {},
})

export const useChatContext = () => {
  return useContext(chatContext)
}

export const ChatProvider = ({ children }: any) => {
  const [messageHistory, setMessageHistory] = useState<ChatMessage[]>([])
  const [directMessages, setDirectMessages] = useState<DirectMessages>({})
  const [files, setFiles] = useState<Map<string, ChatFile>>(new Map<string, ChatFile>())
  const [roomId, setRoomId] = useState<Chatroom>('')
  const [activeVideoCall, setActiveVideoCall] = useState<string | null>(null)

  const { libp2p } = useLibp2pContext()

  // Load message history when component mounts
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const messages = await messageStore.getMessagesByTopic(CHAT_TOPIC)
        if (messages.length > 0) {
          setMessageHistory(messages)
        }
      } catch (error) {
        log('Error loading message history:', error)
      }
    }
    loadHistory()
  }, [setMessageHistory])

  const messageCB = (evt: CustomEvent<Message>) => {
    // FIXME: Why does 'from' not exist on type 'Message'?
    const { topic, data } = evt.detail

    switch (topic) {
      case CHAT_TOPIC: {
        chatMessageCB(evt, topic, data)
        break
      }
      case CHAT_FILE_TOPIC: {
        chatFileMessageCB(evt, topic, data)
        break
      }
      case PUBSUB_PEER_DISCOVERY: {
        break
      }
      default: {
        console.error(`Unexpected event %o on gossipsub topic: ${topic}`, evt)
      }
    }
  }

  const chatMessageCB = async (evt: CustomEvent<Message>, topic: string, data: Uint8Array) => {
    const msg = new TextDecoder().decode(data)
    log(`${topic}: ${msg}`)

    // Append signed messages, otherwise discard
    if (evt.detail.type === 'signed') {
      const message = {
        msgId: crypto.randomUUID(),
        msg,
        fileObjectUrl: undefined,
        peerId: evt.detail.from.toString(),
        read: false,
        receivedAt: Date.now(),
      }

      // Store message in IndexedDB
      await messageStore.storeMessage(topic, message)

      // Update UI state
      setMessageHistory([
        ...messageHistory,
        message
      ])
    }
  }

  const chatFileMessageCB = async (evt: CustomEvent<Message>, topic: string, data: Uint8Array) => {
    const newChatFileMessage = (id: string, body: Uint8Array) => {
      return `File: ${id} (${body.length} bytes)`
    }
    const fileId = new TextDecoder().decode(data)

    // if the message isn't signed, discard it.
    if (evt.detail.type !== 'signed') {
      return
    }
    const senderPeerId = evt.detail.from

    try {
      const stream = await libp2p.dialProtocol(senderPeerId, FILE_EXCHANGE_PROTOCOL)
      await pipe(
        [uint8ArrayFromString(fileId)],
        (source) => lp.encode(source),
        stream,
        (source) => lp.decode(source),
        async function (source) {
          for await (const data of source) {
            const body: Uint8Array = data.subarray()
            log(`chat file message request_response: response received: size:${body.length}`)

            const msg: ChatMessage = {
              msgId: crypto.randomUUID(),
              msg: newChatFileMessage(fileId, body),
              fileObjectUrl: window.URL.createObjectURL(new Blob([body])),
              peerId: senderPeerId.toString(),
              read: false,
              receivedAt: Date.now(),
            }
            setMessageHistory([...messageHistory, msg])
          }
        },
      )
    } catch (e) {
      console.error(e)
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
        fileObjectUrl: undefined,
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

    // Handle incoming video calls
    const handleIncomingCall = (evt: CustomEvent<{ peerId: PeerId }>) => {
      const peerId = evt.detail.peerId.toString()
      setActiveVideoCall(peerId)
    }
    libp2p.services.videoCall.addEventListener('incomingCall', handleIncomingCall)

    // Handle call ended
    const handleCallEnded = () => {
      setActiveVideoCall(null)
    }
    libp2p.services.videoCall.addEventListener('callEnded', handleCallEnded)

    libp2p.handle(FILE_EXCHANGE_PROTOCOL, ({ stream }) => {
      pipe(
        stream.source,
        (source) => lp.decode(source),
        (source) =>
          map(source, async (msg) => {
            const fileId = uint8ArrayToString(msg.subarray())
            const file = files.get(fileId)!
            return file.body
          }),
        (source) => lp.encode(source),
        stream.sink,
      )
    })

    return () => {
      ;(async () => {
        // Cleanup handlers 👇
        libp2p.services.pubsub.removeEventListener('message', messageCB)
        libp2p.services.videoCall.removeEventListener('incomingCall', handleIncomingCall)
        libp2p.services.videoCall.removeEventListener('callEnded', handleCallEnded)
        await libp2p.unhandle(FILE_EXCHANGE_PROTOCOL)
      })()
    }
  }, [libp2p, files, messageCB])

  const initiateVideoCall = async (peerId: string) => {
    try {
      await libp2p.services.videoCall.initiateCall(peerIdFromString(peerId))
      setActiveVideoCall(peerId)
    } catch (err) {
      log('Failed to initiate video call:', err)
      throw err
    }
  }

  return (
    <chatContext.Provider
      value={{
        roomId,
        setRoomId,
        messageHistory,
        setMessageHistory,
        directMessages,
        setDirectMessages,
        files,
        setFiles,
        activeVideoCall,
        setActiveVideoCall,
        initiateVideoCall,
      }}
    >
      {children}
    </chatContext.Provider>
  )
}
