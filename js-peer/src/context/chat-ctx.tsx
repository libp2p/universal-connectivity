import React, { createContext, useContext, useState } from 'react'

export interface ChatMessage {
  msgId: string
  msg: string
  fileObjectUrl: string | undefined
  from: 'me' | 'other'
  peerId: string
  read: boolean
}

export interface DMMessages {
  [peerId: string]: ChatMessage[]
}

export type Chatroom = string

export interface ChatContextInterface {
  messageHistory: ChatMessage[]
  setMessageHistory: (messageHistory: ChatMessage[]) => void
  dmMessages: DMMessages
  setDMMessages: (dmMessages: DMMessages) => void
  chatRoom: Chatroom
  setChatRoom: (chatRoom: Chatroom) => void
}
export const chatContext = createContext<ChatContextInterface>({
  messageHistory: [],
  setMessageHistory: () => {},
  dmMessages: {},
  setDMMessages: () => {},
  chatRoom: '',
  setChatRoom: () => {},
})

export const useChatContext = () => {
  return useContext(chatContext)
}

export const ChatProvider = ({ children }: any) => {
  const [messageHistory, setMessageHistory] = useState<ChatMessage[]>([])
  const [dmMessages, setDMMessages] = useState<DMMessages>({})
  const [chatRoom, setChatRoom] = useState<Chatroom>('')

  return (
    <chatContext.Provider
      value={{
        chatRoom,
        setChatRoom,
        dmMessages,
        setDMMessages,
        messageHistory,
        setMessageHistory,
      }}
    >
      {children}
    </chatContext.Provider>
  )
}
