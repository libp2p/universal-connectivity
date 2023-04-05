import { createLibp2p, Libp2p } from 'libp2p'
import { noise } from '@chainsafe/libp2p-noise'
import { yamux } from '@chainsafe/libp2p-yamux'
import { bootstrap } from '@libp2p/bootstrap'
import { MemoryDatastore } from 'datastore-core'
import { peerIdFromString } from '@libp2p/peer-id'
import { kadDHT } from '@libp2p/kad-dht'
import type { PeerInfo } from '@libp2p/interface-peer-info'
import {
  multiaddr,
  Multiaddr,
  protocols,
  Protocol,
} from '@multiformats/multiaddr'
import { sha256 } from 'multiformats/hashes/sha2'
import type { Message } from '@libp2p/interface-pubsub'
import { LevelDatastore } from 'datastore-level'
import isIPPrivate from 'private-ip'
import { delegatedPeerRouting } from '@libp2p/delegated-peer-routing'
import { create as KuboClient } from 'kubo-rpc-client'
import { gossipsub } from '@chainsafe/libp2p-gossipsub'
import { webSockets } from '@libp2p/websockets'
import { webTransport } from '@libp2p/webtransport'
import { webRTC, webRTCDirect } from '@libp2p/webrtc'
import { PeerId } from 'kubo-rpc-client/dist/src/types'
import { CHAT_TOPIC, CIRCUIT_RELAY_CODE, WEBRTC_CODE } from './constants'
import * as filters from "@libp2p/websockets/filters"

// @ts-ignore
import { circuitRelayTransport } from 'libp2p/circuit-relay'


export async function startLibp2p(options: {} = {}) {
  // localStorage.debug = 'libp2p*,-*:trace'
  // application-specific data lives in the datastore
  // const datastore = new MemoryDatastore()
  const datastore = new LevelDatastore('js-libp2p-nextjs-example')

  // default is to use ipfs.io
  const client = KuboClient({
    // use default api settings
    protocol: 'https',
    port: 443,
    host: 'node0.delegate.ipfs.io',
  })

  // libp2p is the networking layer that underpins Helia
  const libp2p = await createLibp2p({
    // dht: kadDHT(),
    datastore,
    transports: [webTransport(), webSockets({
      filter: filters.all,
    }), webRTC({
      rtcConfiguration: {
        iceServers:[
          {
            urls: [
              'stun:stun.l.google.com:19302',
              'stun:global.stun.twilio.com:3478'
            ]
          }
        ]
      }
    }), webRTCDirect(), circuitRelayTransport({
      discoverRelays: 1,
    }),],
    // transports: [webRTC()],
    connectionEncryption: [noise()],
    streamMuxers: [yamux()],
    // connectionGater: {
    //   denyDialMultiaddr: (peerId: PeerId, multiaddr: Multiaddr) => {
    //     const { host } = multiaddr.toOptions()
    //     // Avoid dialing private IPs
    //     if (isIPPrivate(host)) {
    //       return true
    //     }

    //     return false
    //   },
    // },
    peerDiscovery: [
      // bootstrap({
      //   list: [
      //     // '/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN',
      //     // '/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa',
      //     // '/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt',
      //     // '/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb',
      //   ],
      // }),
    ],
    pubsub: gossipsub({
      allowPublishToZeroPeers: true,
      // allowedTopics: [CHAT_TOPIC],
      msgIdFn: msgIdFnStrictNoSign,
      ignoreDuplicatePublishError: true,
    }),
    // connectionManager: {
    //   minConnections: 0,
    //   maxConnections: 3,
    // },
    // peerRouters: [delegatedPeerRouting(client)],
  })

  libp2p.pubsub.subscribe(CHAT_TOPIC)

  libp2p.peerStore.addEventListener('change:multiaddrs', ({detail: {peerId, multiaddrs}}) => {
    console.log(`changed multiaddrs: peer ${peerId} multiaddrs: ${multiaddrs}`)
    setWebRTCDirectAddress(multiaddrs, peerId.toString())
  })

  console.log(`this nodes peerID: ${libp2p.peerId.toString()}`)

  return libp2p
}

// message IDs are used to dedup inbound messages
// every agent in network should use the same message id function
// messages could be perceived as duplicate if this isnt added (as opposed to rust peer which has unique message ids)
export async function msgIdFnStrictNoSign(msg: Message): Promise<Uint8Array> {
  return await sha256.encode(msg.data)
}

// Curried function to get multiaddresses for a peer by looking up dht
export const getPeerMultiaddrsFromDHT =
  (libp2p: Libp2p) =>
  async (peerId: string): Promise<Multiaddr[]> => {
    const peer = peerIdFromString(peerId)

    let multiaddrs: Multiaddr[]

    outer: while (true) {
      try {
        // 👇 How does `dht.findPeer` work when in client mode?
        // IIUC, `libp2p.dht.findPeer` sends a DHT client request to one of the bootstrap nodes it manages to connect to
        // Main constraint is that in secure context can only connect to peers with a TLS certificate, WebRTC peers, or WebTransport peers
        for await (const event of libp2p.dht.findPeer(peer)) {
          console.log('findPeer event: ', event)
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

// Method that returns multiaddrs for a given peer
export const getPeerMultiaddrs =
  (libp2p: Libp2p) =>
  async (peerId: string): Promise<Multiaddr[]> => {
    const peer = peerIdFromString(peerId)
    let peerInfo: PeerInfo

    while (true) {
      try {
        peerInfo = await libp2p.peerRouting.findPeer(peer)
        break
      } catch (e) {
        console.log(e)
      }
      console.log('wait 10 seconds before next dht lookup')
      await new Promise((resolve, reject) => {
        setTimeout(() => resolve(null), 10 * 1000)
      })
    }

    return peerInfo.multiaddrs
  }

// Attempt to connect to an array of multiaddrs
export const connectToMultiaddrs =
  (libp2p: Libp2p) => async (multiaddrs: Multiaddr[], peerId: string) => {
    const publicWebTransportMultiaddrs = filterPublicMultiaddrs(multiaddrs)

    if (publicWebTransportMultiaddrs.length === 0) {
      throw new Error('No Public WebTransport multiaddrs found for this peer')
    }

    const conns = []
    const errs = []
    for (let multiaddr of publicWebTransportMultiaddrs) {
      multiaddr = addPeerIdToWebTransportMultiAddr(multiaddr, peerId)
      console.log(`dialling: ${multiaddr.toString()}`)
      try {
        const conn = await libp2p.dial(multiaddr)
        conns.push(conn)
        console.info('connected to', conn.remotePeer, 'on', conn.remoteAddr)
      } catch (e) {
        errs.push(e)
        console.error(e)
      }
    }
    if (conns.length === 0) {
      throw new Libp2pDialError('Failed to connect to peer', errs)
    }
    return conns
  }

// Attempt to connect to an array of multiaddrs
export const connectToMultiaddr =
  (libp2p: Libp2p) => async (multiaddr: Multiaddr) => {
    console.log(`dialling: ${multiaddr.toString()}`)
    try {
      const conn = await libp2p.dial(multiaddr)
      console.info('connected to', conn.remotePeer, 'on', conn.remoteAddr)
      return conn
    } catch (e) {
      console.error(e)
      throw e
    }
  }

/**
 * Returns a filtered list of public multiaddrs of a specific protocol
 *
 * @param multiaddrs multiaddrs to filter out
 * @param selectedProtocol protoc
 * @returns
 */
export const filterPublicMultiaddrs = (
  multiaddrs: Multiaddr[],
  selectedProtocol: Protocol = protocols('webtransport'),
): Multiaddr[] => {
  return (
    multiaddrs
      // Filter out private IPs
      .filter((multiaddr) => {
        return !isIPPrivate(multiaddr.toOptions().host)
      })
      // Could be done more easily with https://github.com/multiformats/js-mafmt
      .filter((addr) => {
        const res = addr
          .protoCodes()
          .filter((pt) => protocols(pt)?.name === selectedProtocol.name)

        return res.length > 0
      })
  )
}

// Add the peer ID to the multiaddr so that it can connect
// Because multiaddrs aren't returned with the PeerID in them
// from the libp2p.dht.findPeer call
export const addPeerIdToWebTransportMultiAddr = (
  addr: Multiaddr,
  peerId: string,
): Multiaddr => {
  if (addr.toString().includes('/p2p')) return addr

  return multiaddr(`${addr.toString()}/p2p/${peerId}`)
}
/**
 * Custom Libp2p Dial Error that can hold an array of dial error objects
 */
export class Libp2pDialError extends Error {
  // error can be an array of dial errors
  error: object
  constructor(message: string, error: object) {
    super(message)
    Object.setPrototypeOf(this, Libp2pDialError.prototype)
    this.error = error
  }
}

export const setWebRTCDirectAddress = (maddrs: Multiaddr[], peerId: string) => {
  maddrs.forEach((maddr) => {
    if (maddr.protoCodes().includes(CIRCUIT_RELAY_CODE)) {
      if (maddr.protos().pop()?.name === 'p2p') {
          maddr = maddr.decapsulateCode(protocols('p2p').code)
      }

      const webrtcDirectAddress = multiaddr(maddr.toString() + '/webrtc/p2p/' + peerId)

      console.log(`Listening on '${webrtcDirectAddress.toString()}'`)
    }
  })
}


export const isWebrtc = (ma: Multiaddr) => {
  return ma.protoCodes().includes(WEBRTC_CODE)
}