import { useEffect, useCallback } from 'react'
import { ChatMessage, useChatContext } from '@/context/chat-ctx'

export const useMarkAsRead = (msgId: string, peerId: string, read: boolean, dm: boolean) => {
  const { messageHistory, setMessageHistory, directMessages, setDirectMessages } = useChatContext()

  const markAsRead = useCallback((messages: ChatMessage[], msgId: string): ChatMessage[] => {
    return messages.map((m) => (m.msgId === msgId ? { ...m, read: true } : m))
  }, [])

  useEffect(() => {
    if (read) {
      return
    }

    if (dm) {
      const updatedDMs = directMessages[peerId]

      if (updatedDMs.some((m) => m.msgId === msgId && !m.read)) {
        setDirectMessages((prev) => ({
          ...prev,
          [peerId]: markAsRead(updatedDMs, msgId),
        }))
      }
    } else {
      if (messageHistory.some((m) => m.msgId === msgId && !m.read)) {
        setMessageHistory((prev) => markAsRead(prev, msgId))
      }
    }
  }, [dm, directMessages, messageHistory, msgId, peerId, read, setDirectMessages, setMessageHistory, markAsRead])
}
