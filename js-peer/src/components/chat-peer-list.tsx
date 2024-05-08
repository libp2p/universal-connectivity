import { useLibp2pContext } from '@/context/ctx'
import { CHAT_TOPIC } from '@/lib/constants'
import React, { useEffect, useState } from 'react'
import type { PeerId } from '@libp2p/interface'
import Blockies from 'react-18-blockies'

export function ChatPeerList() {
  const { libp2p } = useLibp2pContext()
  const [subscribers, setSubscribers] = useState<PeerId[]>([])

  useEffect(() => {
    const onSubscriptionChange = () => {
      const subscribers = libp2p.services.pubsub.getSubscribers(CHAT_TOPIC)
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
      <h2 className="my-2 mb-2 ml-2 text-lg text-gray-600">Peers</h2>
      <ul className="overflow-auto h-[32rem]">
        {<Peer key={libp2p.peerId.toString()} peer={libp2p.peerId} self />}
        {subscribers.map((p) => (
          <Peer key={p.toString()} peer={p} self={false} />
        ))}
      </ul>
    </div>
  )
}

function Peer({ peer, self }: { peer: PeerId; self: boolean }) {
  return (
    <li className="flex items-center px-3 py-2 text-sm transition duration-150 ease-in-out border-b border-gray-300 focus:outline-none">
      <Blockies seed={peer.toString()} size={15} scale={3} className="rounded max-h-10 max-w-10" />
      <div className="w-full pb-2">
        <div className="flex justify-between">
          <span className={`block ml-2 font-semibold ${self ? 'text-indigo-700-600' : 'text-gray-600'}`}>
            {peer.toString().slice(-7)}
            {self && ' (You)'}
          </span>
        </div>
      </div>
    </li>
  )
}
