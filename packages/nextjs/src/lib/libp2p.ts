import { createLibp2p, Libp2p } from 'libp2p'
import { noise } from '@chainsafe/libp2p-noise'
import { yamux } from '@chainsafe/libp2p-yamux'
import { webTransport } from '@libp2p/webtransport'
import { bootstrap } from '@libp2p/bootstrap'
import { MemoryDatastore } from 'datastore-core'

import { peerIdFromString } from '@libp2p/peer-id'
import { kadDHT } from '@libp2p/kad-dht'
import type { PeerInfo } from '@libp2p/interface-peer-info'
import type { Multiaddr } from '@multiformats/multiaddr'
import { LevelDatastore } from 'datastore-level'
import { webSockets } from '@libp2p/websockets'

export async function startLibp2p() {
  // application-specific data lives in the datastore
  // const datastore = new MemoryDatastore()
  const datastore = new LevelDatastore('js-libp2p-nextjs-example')

  // libp2p is the networking layer that underpins Helia
  const libp2p = await createLibp2p({
    dht: kadDHT(),
    datastore,
    transports: [webTransport(), webSockets()],
    connectionEncryption: [noise()],
    streamMuxers: [yamux()],
    peerDiscovery: [
      bootstrap({
        list: [
          '/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN',
          '/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa',
          '/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb',
          '/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt',
        ],
      }),
    ],
  })

  console.log(`this nodes peerID: ${libp2p.peerId.toString()}`)
  return libp2p
}

// Curried function to get multiaddresses for a peer by looking up dht
export const getPeerMultiaddrs =
  (libp2p: Libp2p) =>
  async (peerId: string): Promise<Multiaddr[]> => {
    const peer = peerIdFromString(peerId)

    let multiaddr: Multiaddr[]
    let peerInfo: PeerInfo

    outer: while (true) {
      console.log(libp2p)
      try {
        // 👇 How does `dht.findPeer` work when in client mode?
        for await (const event of libp2p.dht.findPeer(peer)) {
          console.log(event)
          if (event.name === 'FINAL_PEER') {
            peerInfo = event.peer
            break outer
          }
        }
      } catch (e) {
        console.log(e)
      }
      console.log('wait 5 seconds before next dht lookup')
      await new Promise((resolve, reject) => {
        setTimeout(() => resolve(null), 5000)
      })
    }

    return peerInfo.multiaddrs
  }

export const connectToPeer =
  (libp2p: Libp2p) => async (multiaddrs: Multiaddr[]) => {
    // '12D3KooWBdmLJjhpgJ9KZgLM3f894ff9xyBfPvPjFNn7MKJpyrC2', // lidel's IPFS node with Webtransport
    // '12D3KooWRBy97UB99e3J6hiPesre1MZeuNQvfan4gBziswrRJsNK', // local node

    // Establish a connection using a stable PeerID

    for (const multiaddr of multiaddrs) {
      console.log(multiaddr)
      try {
        const conn = await libp2p.dial(multiaddr)
        console.log(conn)
      } catch (e) {
        console.log(e)
      }
    }
  }
