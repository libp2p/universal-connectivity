import React, { createContext, useContext, useEffect, useState } from 'react';
import { useLibp2pContext } from './ctx';
import type { Message, PeerId } from '@libp2p/interface';
import { peerIdFromString } from '@libp2p/peer-id';
import {
  CHAT_FILE_TOPIC,
  CHAT_TOPIC,
  FILE_EXCHANGE_PROTOCOL,
  MIME_TEXT_PLAIN,
  PUBSUB_PEER_DISCOVERY,
} from '@/lib/constants';
import { toString as uint8ArrayToString, fromString as uint8ArrayFromString } from 'uint8arrays';
import { pipe } from 'it-pipe';
import map from 'it-map';
import { encode, decode } from 'it-length-prefixed';
import { forComponent } from '@/lib/logger';
import { messageStore } from '@/lib/message-store';
import { DirectMessageEvent, directMessageEvent } from '@/lib/direct-message';

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
      console.log('Loading message history...');
      console.log('Loading public chat messages...');
      const chatMessages = await messageStore.getMessagesByTopic(CHAT_TOPIC);
      console.log(`Loaded ${chatMessages.length} public chat messages.`);
      console.log('Loading file messages...');
      const fileMessages = await messageStore.getMessagesByTopic(CHAT_FILE_TOPIC);
      console.log(`Loaded ${fileMessages.length} file messages.`);
      console.log('Merging and sorting messages...');
      const allMessages = [...chatMessages, ...fileMessages].sort((a, b) => a.receivedAt - b.receivedAt);
      console.log(`Total messages to set: ${allMessages.length}`);
      console.log('Setting message history...');
      if (allMessages.length > 0) {
        setMessageHistory(allMessages)
      }
      console.log('Message history loaded.');
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

      console.log('Received chat message:', message);
      console.log('Storing message in IndexedDB...');
      try {
        // Store message in IndexedDB
        await messageStore.storeMessage(topic, message)

        // Update UI state using function form to avoid race conditions
        setMessageHistory(prevMessages => [...prevMessages, message])
      } catch (error) {
        console.error('Error storing message:', error);
        log('Error storing message:', error)
        // Still update UI state even if storage fails
        setMessageHistory(prevMessages => [...prevMessages, message])
      }
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

    console.log('Received file message from:', senderPeerId.toString());
    console.log('File message ID:', fileId);
    console.log('Received file message from:', senderPeerId.toString());
    console.log('File message ID:', fileId);

    try {
      const stream = await libp2p.dialProtocol(senderPeerId, FILE_EXCHANGE_PROTOCOL)
      await pipe(
        [uint8ArrayFromString(fileId)],
        (source) => encode(source),
        stream,
        (source) => decode(source),
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
            console.log('Storing file message in IndexedDB...');
            try {
              // Store file message in IndexedDB
              await messageStore.storeMessage(CHAT_FILE_TOPIC, msg)
              
              // Update UI state using function form to avoid race conditions
              setMessageHistory(prevMessages => [...prevMessages, msg])
            } catch (error) {
              console.error('Error storing file message:', error);
              log('Error storing file message:', error)
              console.error('Error handling file message:', error);
              log('Error handling file message:', error)
              // Still update UI state even if storage fails
              setMessageHistory(prevMessages => [...prevMessages, msg])
            }
          }
        },
      )
    } catch (e) {
      console.error('Error handling file message:', e);
      log('Error handling file message:', e)
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
        (source) => decode(source),
        (source) =>
          map(source, async (msg) => {
            const fileId = uint8ArrayToString(msg.subarray())
            const file = files.get(fileId)!
            return file.body
          }),
        (source) => encode(source),
        stream.sink,
      )
    })

    return () => {
      ;(async () => {
        // Cleanup handlers 
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
      console.error('Error initiating video call:', err);
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
