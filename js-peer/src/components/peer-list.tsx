import { XCircleIcon } from '@heroicons/react/24/solid'
import type { PeerId, Connection } from '@libp2p/interface'
import { Badge } from './badge'
import { useCallback } from 'react'
import { useLibp2pContext } from '@/context/ctx'

interface PeerListProps {
  connections: Connection[]
}

export default function PeerList({ connections }: PeerListProps) {
  return (
    <ul role="list" className="divide-y divide-gray-100">
      {connections.map((connection) => (
        <Peer key={connection.id} connection={connection} />
      ))}
    </ul>
  )
}

interface PeerProps {
  connection: Connection
}
function Peer({ connection }: PeerProps) {
  const { libp2p } = useLibp2pContext()

  const handleDisconnectPeer = useCallback(
    (peerId: PeerId) => {
      libp2p.hangUp(peerId)
    },
    [libp2p],
  )

  let ipAddr
  try {
    const nodeAddr = connection.remoteAddr?.nodeAddress()
    ipAddr = `${nodeAddr.address}:${nodeAddr.port} |`
  } catch (e) {
    ipAddr = null
  }

  return (
    <li key={connection.id} className="flex justify-between gap-x-6 py-3">
      <div className="flex min-w-0 gap-x-4">
        <div className="mt-1 flex items-center gap-x-1.5">
          <div className="flex-none rounded-full bg-emerald-500/20 p-1">
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          </div>
        </div>
        {/* <img className="h-12 w-12 flex-none rounded-full bg-gray-50" src={person.imageUrl} alt="" /> */}
        <div className="min-w-0 flex-auto">
          <p className="text-sm font-semibold leading-6 text-gray-900">
            {connection.remotePeer.toString()}{' '}
            {connection.remoteAddr.protoNames().includes('webrtc') ? <Badge color="indigo">P2P Browser</Badge> : null}
          </p>
          <p className="mt-1 truncate text-xs leading-5 text-gray-500">
            {ipAddr} {connection.remoteAddr.protoNames().join(', ')}
          </p>
        </div>
      </div>

      {/* <div className="flex gap-x-2 items-center "> */}
      <div className="hidden  sm:flex sm:flex-col sm:items-end">
        <button
          onClick={() => handleDisconnectPeer(connection.remotePeer)}
          className="bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded flex flex-row"
        >
          <XCircleIcon className="w-6 h-6" />
          <span className="pl-1">Disconnect</span>
        </button>
      </div>
    </li>
  )
}
