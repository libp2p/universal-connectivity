import CubeTransparentIcon from '@heroicons/react/24/outline/CubeTransparentIcon'
import { useEffect } from 'react'
import Blockies from 'react-18-blockies'
import { useLibp2pContext } from '@/context/ctx'
import { usePeerContext } from '@/context/peer-ctx'
import {
  PeerProtoTuple,
  getFormattedConnections,
  shortPeerId,
} from '@/lib/peers'

export interface Props {
  showShortPeerId?: boolean
}

export const ConnectedPeerList = ({ showShortPeerId }: Props) => {
  const { peerStats, setPeerStats } = usePeerContext()
  const { libp2p } = useLibp2pContext()

  useEffect(() => {
    const interval = setInterval(() => {
      const connections = libp2p.getConnections()

      setPeerStats({
        ...peerStats,
        peerIds: connections.map((conn) => conn.remotePeer),
        connections: connections,
        connected: connections.length > 0,
      })
    }, 1000)

    return () => {
      clearInterval(interval)
    }
  }, [libp2p, peerStats, setPeerStats])

  const peerConn = (peerProto: PeerProtoTuple, idx: number) => {
    return (
      <div key={idx} className="p-1">
        <div className="flex">
          <Blockies
            seed={peerProto.peerId}
            size={15}
            scale={3}
            className="rounded mr-2 max-h-10 max-w-10"
          />
          {showShortPeerId ? shortPeerId(peerProto.peerId) : peerProto.peerId} (
          {peerProto.protocols.join(', ')})
        </div>
      </div>
    )
  }

  return peerStats.peerIds.length > 0 ? (
    <div>
      <div className="flex">
        <CubeTransparentIcon className="w-6 h-6 text-gray-400 mr-1" />
        <h3 className="font-bold text-gray-600">
          Connected peers (
          {getFormattedConnections(peerStats.connections).length})
        </h3>
      </div>
      <div className="px-2">
        {getFormattedConnections(peerStats.connections).map((pair, idx) =>
          peerConn(pair, idx),
        )}
      </div>
    </div>
  ) : null
}
