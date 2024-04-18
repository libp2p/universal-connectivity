import { useLibp2pContext } from "@/context/ctx"
import { usePeerContext } from "@/context/peer-ctx"
import { getFormattedConnections, shortPeerId } from "@/lib/peers"
import { useEffect } from "react"

export const ConnectedPeerList = () => {
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

  return (
    peerStats.peerIds.length > 0 ? (
      <div>
        <h3 className="text-xl">
          {' '}
          Connected peers ({getFormattedConnections(peerStats.connections).length})
        </h3>
        <div className="px-2">
          {getFormattedConnections(peerStats.connections)
            .map(
              (pair) =>
                `${shortPeerId(pair.peerId)} (${pair.protocols.join(', ')})`,
            )
            .join('\n')}
        </div>
      </div>
    ) : null
  )
}
