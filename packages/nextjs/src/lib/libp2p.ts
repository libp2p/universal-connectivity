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
import isIPPrivate from 'private-ip'

import { webSockets } from '@libp2p/websockets'

export async function startLibp2p() {
  // localStorage.debug = 'libp2p*,-*:trace'
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
          // '/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa',
          '/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt',
          '/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb',
          // '/dns4/am6.bootstrap.libp2p.io/tcp/443/wss/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb',
          // '/dns4/node0.preload.ipfs.io/tcp/443/wss/p2p/QmZMxNdpMkewiVZLMRxaNxUeZpDUb34pWjZ1kZvsd16Zic',
          // '/dns4/node1.preload.ipfs.io/tcp/443/wss/p2p/Qmbut9Ywz9YEDrz8ySBSgWyJk41Uvm2QJPhwDJzJyGFsD6',
          // '/dns4/node2.preload.ipfs.io/tcp/443/wss/p2p/QmV7gnbW5VTcJ3oyM2Xk1rdFBJ3kTkvxc87UFGsun29STS',
          // '/dns4/node3.preload.ipfs.io/tcp/443/wss/p2p/QmY7JB6MQXhxHvq7dBDh4HpbH29v4yE9JRadAVpndvzySN'
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

    let multiaddrs: Multiaddr[]

    outer: while (true) {
      try {
        // 👇 How does `dht.findPeer` work when in client mode?
        // IIUC, `libp2p.dht.findPeer` sends a DHT client request to one of the bootstrap nodes it manages to connect to
        for await (const event of libp2p.dht.findPeer(peer)) {
          console.log(event)
          if (event.name === 'FINAL_PEER') {
            multiaddrs = event.peer.multiaddrs
            break outer
          }
        }
      } catch (e) {
        console.log(e)
      }
      console.log('wait 10 seconds before next dht lookup')
      await new Promise((resolve, reject) => {
        setTimeout(() => resolve(null), 10 * 1000)
      })
    }

    return multiaddrs
  }

// Attempt to connect to an array of multiaddrs
export const connectToPeer =
  (libp2p: Libp2p) => async (multiaddrs: Multiaddr[]) => {
    // '12D3KooWBdmLJjhpgJ9KZgLM3f894ff9xyBfPvPjFNn7MKJpyrC2', // lidel's IPFS node with Webtransport
    // '12D3KooWRBy97UB99e3J6hiPesre1MZeuNQvfan4gBziswrRJsNK', // local node

    let errCount = 0
    let conCount = 0

    // Filter out private IPs
    const publicMultiaddrs = multiaddrs.filter((multiaddr) => {
      return !isIPPrivate(multiaddr.toOptions().host)
    })

    for (const multiaddr of publicMultiaddrs) {
      try {
        const conn = await libp2p.dial(multiaddr)
        conCount++
      } catch (e) {
        console.error(e)
        errCount++
      }
    }
    if (conCount === 0) {
      throw new Error('Failed to connect to peer')
    }
  }
