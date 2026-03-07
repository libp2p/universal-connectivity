import { useLibp2pContext } from '@/context/ctx'
import { useEffect, useState } from 'react'
import { PeerId } from '@libp2p/interface'
import { useChatContext } from '@/context/chat-ctx'
import Blockies from 'react-18-blockies'

export interface PeerProps {
  peer: PeerId
  self: boolean
  withName: boolean
  withUnread: boolean
}

export function PeerWrapper({ peer, self, withName, withUnread }: PeerProps) {
  const { libp2p } = useLibp2pContext()
  const [identified, setIdentified] = useState(false)
  const { setRoomId } = useChatContext()

  const handleSetRoomId = () => {
    setRoomId(peer.toString())
  }

  useEffect(() => {
    const init = async () => {
      if (await libp2p.peerStore.has(peer)) {
        const p = await libp2p.peerStore.get(peer)
        if (p.protocols.length > 0) {
          setIdentified(true)
        }
      }
    }

    init()
  }, [libp2p.peerStore, peer])

  if (self || !identified) {
    return <Peer peer={peer} self={self} withName={withName} withUnread={withUnread} />
  }

  if (identified && libp2p.services.directMessage.isDMPeer(peer)) {
    return (
      <div className="relative inline-block text-left cursor-pointer" onClick={() => handleSetRoomId()}>
        <Peer peer={peer} self={self} withName={withName} withUnread={withUnread} />
      </div>
    )
  }

  if (identified && !libp2p.services.directMessage.isDMPeer(peer)) {
    return (
      <div className="relative inline-block text-left group">
        <Peer peer={peer} self={self} withName={withName} withUnread={withUnread} />
        <div className="absolute top-10 left-5 scale-0 rounded bg-white border text-gray-600 p-2 text-xs group-hover:scale-100 z-10">
          Direct{'\u00A0'}message unsupported
        </div>
      </div>
    )
  }
}

export function Peer({ peer, self, withName, withUnread }: PeerProps) {
  const { directMessages } = useChatContext()

  return (
    <div className="flex items-stretch text-sm transition duration-150 ease-in-out focus:outline-none relative text-left">
      <Blockies seed={peer.toString()} size={15} scale={3} className="rounded max-h-10 max-w-10" />
      {withName && (
        <div className="w-full">
          <div className="flex justify-between">
            <span className={`block ml-2 font-semibold ${self ? 'text-indigo-700-600' : 'text-gray-600'}`}>
              {peer.toString().slice(-7)}
              {self && ' (You)'}
            </span>
          </div>
          {withUnread && (
            <div className="ml-2 text-gray-600">
              {directMessages[peer.toString()]?.filter((m) => !m.read).length
                ? `(${directMessages[peer.toString()]?.filter((m) => !m.read).length} unread)`
                : ''}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
