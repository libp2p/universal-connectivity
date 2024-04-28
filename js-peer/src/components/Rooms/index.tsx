import ChatBubbleLeftIcon from '@heroicons/react/24/outline/ChatBubbleLeftIcon'
import { useEffect, useState } from 'react'
import { useChatContext } from '@/context/chat-ctx'

export const Rooms = () => {
  const { setChatRoom, messageHistory } = useChatContext()
  const [unreadMessagesCount, setUnreadMessagesCount] = useState(0)

  const handleRoomChange = () => {
    setChatRoom('')
  }

  useEffect(() => {
    setUnreadMessagesCount(
      messageHistory.filter((msg) => msg.read === false).length,
    )
  }, [messageHistory])

  return (
    <>
      <div className="flex">
        <ChatBubbleLeftIcon className="w-6 h-6 text-gray-400 mr-1" />
        <h3 className="font-bold text-gray-600">Rooms</h3>
      </div>
      <span className="cursor-pointer" onClick={handleRoomChange}>
        Public {unreadMessagesCount !== 0 && <>({unreadMessagesCount})</>}
      </span>
    </>
  )
}
