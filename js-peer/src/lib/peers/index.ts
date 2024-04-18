import type { Connection } from '@libp2p/interface'

export type PeerProtoTuple = {
  peerId: string
  protocols: string[]
}

export const getFormattedConnections = (connections: Connection[]): PeerProtoTuple[] => {
  const protoNames: Map<string, string[]> = new Map()

  connections.forEach((conn) => {
    const exists = protoNames.get(conn.remotePeer.toString())
    const dedupedProtonames = [...new Set(conn.remoteAddr.protoNames())]

    if (exists?.length) {
      const namesToAdd = dedupedProtonames.filter((name) => !exists.includes(name))
      // console.log('namesToAdd: ', namesToAdd)
      protoNames.set(conn.remotePeer.toString(), [...exists, ...namesToAdd])

    } else {
      protoNames.set(conn.remotePeer.toString(), dedupedProtonames)
    }
  })

  return [...protoNames.entries()].map(([peerId, protocols]) => ({
    peerId,
    protocols,
  }))
}

export const shortPeerId = (peerId: string): string => {
  return peerId.slice(-4)
}
