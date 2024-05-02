import React, { createContext, useContext, useState } from 'react'

export interface ChatMessage {
  msgId: string
  msg: string
  fileObjectUrl: string | undefined
  from: 'me' | 'other'
  peerId: string
  read: boolean
  receivedAt: number
}

export interface DirectMessages {
  [peerId: string]: ChatMessage[]
}

export type Chatroom = string

export interface ChatContextInterface {
  messageHistory: ChatMessage[]
  setMessageHistory: (
    messageHistory:
      | ChatMessage[]
      | ((prevMessages: ChatMessage[]) => ChatMessage[]),
  ) => void
  directMessages: DirectMessages
  setDirectMessages: (
    directMessages:
      | DirectMessages
      | ((prevMessages: DirectMessages) => DirectMessages),
  ) => void
  chatRoom: Chatroom
  setChatRoom: (chatRoom: Chatroom) => void
}
export const chatContext = createContext<ChatContextInterface>({
  messageHistory: [],
  setMessageHistory: () => {},
  directMessages: {},
  setDirectMessages: () => {},
  chatRoom: '',
  setChatRoom: () => {},
})

export const useChatContext = () => {
  return useContext(chatContext)
}

export const ChatProvider = ({ children }: any) => {
  const [messageHistory, setMessageHistory] = useState<ChatMessage[]>([])
  const [directMessages, setDirectMessages] = useState<DirectMessages>({})
  const [chatRoom, setChatRoom] = useState<Chatroom>('')

  return (
    <chatContext.Provider
      value={{
        chatRoom,
        setChatRoom,
        directMessages,
        setDirectMessages,
        messageHistory,
        setMessageHistory,
      }}
    >
      {children}
    </chatContext.Provider>
  )
}
