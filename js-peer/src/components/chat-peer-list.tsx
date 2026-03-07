import { useLibp2pContext } from '@/context/ctx'
import { CHAT_TOPIC } from '@/lib/constants'
import React, { useEffect, useState } from 'react'
import type { PeerId } from '@libp2p/interface'
import { PeerWrapper } from './peer'

interface ChatPeerListProps {
  hideHeader?: boolean
}

export function ChatPeerList({ hideHeader = false }: ChatPeerListProps) {
  const { libp2p } = useLibp2pContext()
  const [subscribers, setSubscribers] = useState<PeerId[]>([])

  useEffect(() => {
    const onSubscriptionChange = () => {
      const subscribers = libp2p.services.pubsub.getSubscribers(CHAT_TOPIC) as PeerId[]
      setSubscribers(subscribers)
    }
    onSubscriptionChange()
    libp2p.services.pubsub.addEventListener('subscription-change', onSubscriptionChange)
    return () => {
      libp2p.services.pubsub.removeEventListener('subscription-change', onSubscriptionChange)
    }
  }, [libp2p, setSubscribers])

  return (
    <div className="border-l border-gray-300 lg:col-span-1">
      {!hideHeader && <h2 className="my-2 mb-2 ml-2 text-lg text-gray-600">Peers</h2>}
      <div className="overflow-auto h-[20rem] lg:h-[32rem]">
        <div className="px-3 py-2 border-b border-gray-300 focus:outline-none">
          {<PeerWrapper peer={libp2p.peerId} self withName={true} withUnread={false} />}
        </div>
        {subscribers.map((p) => (
          <div key={p.toString()} className="px-3 py-2 border-b border-gray-300 focus:outline-none">
            <PeerWrapper peer={p} self={false} withName={true} withUnread={true} />
          </div>
        ))}
      </div>
    </div>
  )
}
