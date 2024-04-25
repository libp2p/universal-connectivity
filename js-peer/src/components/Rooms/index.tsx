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
      <h1 className="font-bold text-gray-600">Rooms</h1>
      <span className="cursor-pointer" onClick={handleRoomChange}>
        Public {unreadMessagesCount !== 0 && <>({unreadMessagesCount})</>}
      </span>
    </>
  )
}
