import { useEffect } from 'react'
import { ChatMessage, useChatContext } from '@/context/chat-ctx'
import { directMessageEvent } from '@/lib/chat/directMessage/handler'

export const DirectMessageProcessor = () => {
  const { dmMessages, setDMMessages } = useChatContext()

  // inbound chat
  useEffect(() => {
    const handleDirectMessage = async (event: any) => {
      // eslint-disable-next-line no-console
      console.log(directMessageEvent, event)

      const peerId = event.detail.connection.remotePeer.toString()

      const message: ChatMessage = {
        msg: event.detail.request,
        from: 'other',
        read: false,
        msgId: crypto.randomUUID(),
        fileObjectUrl: undefined,
        peerId: peerId,
      }

      const updatedMessages = dmMessages[peerId]
        ? [...dmMessages[peerId], message]
        : [message]

      setDMMessages({
        ...dmMessages,
        [peerId]: updatedMessages,
      })
    }

    // eslint-disable-next-line no-console
    console.log(`adding event listener for ${directMessageEvent}`)
    document.addEventListener(directMessageEvent, handleDirectMessage)

    return () => {
      document.removeEventListener(directMessageEvent, handleDirectMessage)
    }
  }, [dmMessages, setDMMessages])

  return <></>
}
