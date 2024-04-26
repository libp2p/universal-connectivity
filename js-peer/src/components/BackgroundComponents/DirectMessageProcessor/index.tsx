import { useEffect } from 'react'
import { ChatMessage, useChatContext } from '@/context/chat-ctx'
import { directMessageEvent } from '@/lib/chat/directMessage/handler'

export const DirectMessageProcessor = () => {
  const { directMessages, setDirectMessages } = useChatContext()

  // inbound chat
  useEffect(() => {
    const handleDirectMessage = async (event: any) => {
      console.debug(directMessageEvent, event)

      const peerId = event.detail.connection.remotePeer.toString()

      const message: ChatMessage = {
        msg: event.detail.request,
        from: 'other',
        read: false,
        msgId: crypto.randomUUID(),
        fileObjectUrl: undefined,
        peerId: peerId,
      }

      const updatedMessages = directMessages[peerId]
        ? [...directMessages[peerId], message]
        : [message]

      setDirectMessages({
        ...directMessages,
        [peerId]: updatedMessages,
      })
    }

    document.addEventListener(directMessageEvent, handleDirectMessage)

    return () => {
      document.removeEventListener(directMessageEvent, handleDirectMessage)
    }
  }, [directMessages, setDirectMessages])

  return <></>
}
