import { useLibp2pContext } from "@/context/ctx"
import { usePeerContext } from "@/context/peer-ctx"
import { PeerProtoTuple, getFormattedConnections, shortPeerId } from "@/lib/peers"
import { useEffect } from "react"
import Blockies from 'react-18-blockies'

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
        peerIds: connections.map(conn => conn.remotePeer),
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
      <div className="flex" key={idx}>
        <Blockies seed={peerProto.peerId} size={15} scale={3} className="rounded mr-2 max-h-10 max-w-10" />
        {showShortPeerId ? shortPeerId(peerProto.peerId) : peerProto.peerId} ({peerProto.protocols.join(', ')})
      </div>
    )
  }

  return (
    peerStats.peerIds.length > 0 ? (
      <div>
        <h3 className="font-bold text-gray-600">
          Connected peers ({getFormattedConnections(peerStats.connections).length})
        </h3>
        <div className="px-2">
          {getFormattedConnections(peerStats.connections)
            .map(
              (pair, idx) => peerConn(pair, idx)
            )
          }
        </div>
      </div>
    ) : null
  )
}
