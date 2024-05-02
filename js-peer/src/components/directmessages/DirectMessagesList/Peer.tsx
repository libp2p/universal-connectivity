import { useEffect, useState } from 'react'
import { PeerName } from '@/components/Peer'
import { useChatContext } from '@/context/chat-ctx'

interface Props {
  peerId: string
}

export const Peer = ({ peerId }: Props) => {
  const { directMessages } = useChatContext()
  const [unreadMessagesCount, setUnreadMessagesCount] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setUnreadMessagesCount(
        directMessages[peerId].filter((msg) => msg.read === false).length,
      )
    }, 200)

    return () => {
      clearInterval(interval)
    }
  }, [directMessages, peerId])

  return (
    <div className="flex">
      <PeerName peerId={peerId} />
      {unreadMessagesCount !== 0 && (
        <span className="text-sm pl-1">({unreadMessagesCount})</span>
      )}
    </div>
  )
}
