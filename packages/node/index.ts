import { createLibp2p } from 'libp2p'
import { noise } from '@chainsafe/libp2p-noise'
import { yamux } from '@chainsafe/libp2p-yamux'
import { webSockets } from '@libp2p/websockets'
import { tcp } from '@libp2p/tcp'
import { bootstrap } from '@libp2p/bootstrap'
import { MemoryDatastore } from 'datastore-core'
import { peerIdFromString } from '@libp2p/peer-id'
import { kadDHT } from '@libp2p/kad-dht'

// application-specific data lives in the datastore
const datastore = new MemoryDatastore()

// libp2p is the networking layer that underpins Helia
const libp2p = await createLibp2p({
  dht: kadDHT(),
  datastore,
  transports: [webSockets(), tcp()],
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

// Establish a connection using a stable PeerID
const peerId = peerIdFromString(
  '12D3KooWBdmLJjhpgJ9KZgLM3f894ff9xyBfPvPjFNn7MKJpyrC2', // lidel's IPFS node with Webtransport
  // '12D3KooWRBy97UB99e3J6hiPesre1MZeuNQvfan4gBziswrRJsNK', // local node
)

let connection
let multiaddrs

outer: while (true) {
  try {
    // 👇 Where's the spec for how `dht.findPeer` works when in client mode?
    for await (const event of libp2p.dht.findPeer(peerId)) {
      console.log(event)
      if (event.name === 'FINAL_PEER') {
        multiaddrs = event.peer.multiaddrs
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

for (const multiaddr of multiaddrs) {
  console.log(multiaddr)
  try {
    const conn = await libp2p.dial(multiaddr)
    console.log(conn)
  } catch (e) {
    console.log(e)
  }
}
