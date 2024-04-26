import { useEffect, useState } from 'react'
import Blockies from 'react-18-blockies'
import { useChatContext } from '@/context/chat-ctx'
import { shortPeerId } from '@/lib/peers'

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
      <Blockies
        seed={peerId}
        size={15}
        scale={3}
        className="rounded mr-2 max-h-10 max-w-10"
      />
      <div>
        {shortPeerId(peerId)}{' '}
        {unreadMessagesCount !== 0 && <>({unreadMessagesCount})</>}
      </div>
    </div>
  )
}
