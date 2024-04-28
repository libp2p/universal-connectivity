import CloudIcon from '@heroicons/react/24/outline/CloudIcon'
import { Peer } from '@libp2p/interface'
import { useEffect, useState } from 'react'
import PeerName from '../Peer'
import { useLibp2pContext } from '@/context/ctx'

const UPDATE_INTERVAL = 1000

// RecentlySeen is a list of peers from the peerStore
// TODO - use a gossipsub ping to maintain a list of online peers
export const RecentlySeen = () => {
  const { libp2p } = useLibp2pContext()
  const [peers, setPeers] = useState<Peer[]>([])

  useEffect(() => {
    const interval = setInterval(() => {
      const init = async () => {
        if (!libp2p) {
          return
        }

        const peersNew = await libp2p.peerStore.all()

        setPeers(peersNew)
      }

      init()
    }, UPDATE_INTERVAL)

    return () => {
      clearInterval(interval)
    }
  }, [libp2p, peers, setPeers])

  return (
    <>
      <div className="flex">
        <CloudIcon className="w-6 h-6 text-gray-400 mr-1" />
        <h3 className="font-bold text-gray-600">
          Peer Store ({peers.length + 1})
        </h3>
      </div>
      <div className="p-2">
        <PeerName peerId={libp2p.peerId.toString()} me />
      </div>
      {peers.map((peer) => (
        <div key={peer.id.toString()} className="p-2">
          <PeerName peerId={peer.id.toString()} />
        </div>
      ))}
    </>
  )
}
