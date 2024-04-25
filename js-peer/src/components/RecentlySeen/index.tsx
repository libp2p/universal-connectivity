import { Peer } from '@libp2p/interface'
import { useEffect, useState } from 'react'
import PeerName from '../Peer'
import { useLibp2pContext } from '@/context/ctx'

const UPDATE_INTERVAL = 1000

export const RecentlySeen = () => {
  const { libp2p } = useLibp2pContext()
  const [peers, setPeers] = useState<Peer[]>([])

  useEffect(() => {
    const interval = setInterval(() => {
      const init = async () => {
        if (!libp2p) {
          return
        }

        const peers = await libp2p.peerStore.all()

        setPeers(peers)
      }

      init()
    }, UPDATE_INTERVAL)

    return () => {
      clearInterval(interval)
    }
  }, [libp2p, peers, setPeers])

  return (
    <>
      <h3 className="font-bold text-gray-600">
        Recently Seen Peers ({peers.length + 1})
      </h3>
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
