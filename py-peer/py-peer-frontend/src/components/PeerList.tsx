import { XCircleIcon, WifiIcon } from '@heroicons/react/24/outline'
import Blockies from 'react-18-blockies'

interface PeerListProps {
  peers: string[]
}

export default function PeerList({ peers }: PeerListProps) {
  if (peers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-8 text-gray-400 text-sm">
        <WifiIcon className="h-8 w-8" />
        <span>No connected peers yet</span>
      </div>
    )
  }

  return (
    <ul className="divide-y divide-gray-100">
      {peers.map((peerId) => (
        <li key={peerId} className="flex items-center gap-3 py-2.5 px-1">
          <div className="flex-none">
            <Blockies seed={peerId} size={8} scale={4} className="rounded-full" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-mono text-gray-700 truncate">{peerId}</p>
          </div>
          <div className="flex-none">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span className="text-xs text-gray-400">connected</span>
            </span>
          </div>
        </li>
      ))}
    </ul>
  )
}
