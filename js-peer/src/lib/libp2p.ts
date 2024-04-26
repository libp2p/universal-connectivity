import { IDBDatastore } from 'datastore-idb'
import { createDelegatedRoutingV1HttpApiClient } from '@helia/delegated-routing-v1-http-api-client'
import { createLibp2p, Libp2p } from 'libp2p'
import { identify } from '@libp2p/identify'
import {peerIdFromString} from '@libp2p/peer-id'
import { noise } from '@chainsafe/libp2p-noise'
import { yamux } from '@chainsafe/libp2p-yamux'
import { bootstrap } from '@libp2p/bootstrap'
import { Multiaddr } from '@multiformats/multiaddr'
import { sha256 } from 'multiformats/hashes/sha2'
import type { Message, SignedMessage } from '@libp2p/interface'
import { gossipsub } from '@chainsafe/libp2p-gossipsub'
import { webSockets } from '@libp2p/websockets'
import { webTransport } from '@libp2p/webtransport'
import { webRTC, webRTCDirect } from '@libp2p/webrtc'
import { CHAT_FILE_TOPIC, CHAT_TOPIC, WEBRTC_BOOTSTRAP_PEER_ID, WEBTRANSPORT_BOOTSTRAP_PEER_ID } from './constants'
import * as filters from "@libp2p/websockets/filters"
import { circuitRelayTransport } from '@libp2p/circuit-relay-v2'

export async function startLibp2p() {
  // enable verbose logging in browser console to view debug logs
  localStorage.debug = 'libp2p*,-*:trace'

  // application-specific data lives in the datastore
  const datastore = new IDBDatastore('universal-connectivity')

  await datastore.open()

  const libp2p = await createLibp2p({
    datastore,
    addresses: {
      listen: [
        // 👇 Listen for webRTC connection
        '/webrtc'
      ]
    },
    transports: [
      webTransport(),
      webSockets(),
      webRTC({
        rtcConfiguration: {
          iceServers: [{
            // STUN servers help the browser discover its own public IPs
            urls: [
              'stun:stun.l.google.com:19302',
              'stun:global.stun.twilio.com:3478'
            ]
          }]
        }
      }),
      webRTCDirect(),
      // 👇 Required to create circuit relay reservations in order to hole punch browser-to-browser WebRTC connections
      circuitRelayTransport({
        // When set to >0, this will look up the magic CID in order to discover circuit relay peers it can create a reservation with
        discoverRelays: 1,
      })
    ],
    connectionManager: {
      maxConnections: 10,
      minConnections: 3
    },
    connectionEncryption: [noise()],
    streamMuxers: [yamux()],
    connectionGater: {
      denyDialMultiaddr: async () => false,
    },
    // The app-specific go and rust peers use WebTransport and WebRTC-direct which have ephemeral multiadrrs that change.
    // Thus, we dial them using only their peer id below, with delegated routing to discovery their multiaddrs
    // peerDiscovery: [
      // bootstrap({
        // list: [
          // '12D3KooWFhXabKDwALpzqMbto94sB7rvmZ6M28hs9Y9xSopDKwQr'
          // WEBRTC_BOOTSTRAP_NODE,
          // WEBTRANSPORT_BOOTSTRAP_NODE,
          // '/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN',
          // '/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa',
          // '/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb',
          // '/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt',
        // ],
      // }),
    // ],
    services: {
      pubsub: gossipsub({
        allowPublishToZeroTopicPeers: true,
        msgIdFn: msgIdFnStrictNoSign,
        ignoreDuplicatePublishError: true,
      }),
      // Delegated routing helps us discover the ephemeral multiaddrs of the dedicated go and rust bootstrap peers
      // This relies on the public delegated routing endpoint https://docs.ipfs.tech/concepts/public-utilities/#delegated-routing
      delegatedRouting: () => createDelegatedRoutingV1HttpApiClient('https://delegated-ipfs.dev'),
      identify: identify()
    },
  })

  libp2p.services.pubsub.subscribe(CHAT_TOPIC)
  libp2p.services.pubsub.subscribe(CHAT_FILE_TOPIC)

  // Try connecting to bootstrap ppers
  Promise.all([
    libp2p.dial(peerIdFromString(WEBRTC_BOOTSTRAP_PEER_ID)),
    libp2p.dial(peerIdFromString(WEBTRANSPORT_BOOTSTRAP_PEER_ID))
  ])
  .catch(e => {console.log('woot', e)})

  libp2p.addEventListener('self:peer:update', ({ detail: { peer } }) => {
    const multiaddrs = peer.addresses.map(({ multiaddr }) => multiaddr)

    console.log(`changed multiaddrs: peer ${peer.id.toString()} multiaddrs: ${multiaddrs}`)
  })

  return libp2p
}

// message IDs are used to dedupe inbound messages
// every agent in network should use the same message id function
// messages could be perceived as duplicate if this isnt added (as opposed to rust peer which has unique message ids)
export async function msgIdFnStrictNoSign(msg: Message): Promise<Uint8Array> {
  var enc = new TextEncoder();

  const signedMessage = msg as SignedMessage
  const encodedSeqNum = enc.encode(signedMessage.sequenceNumber.toString());
  return await sha256.encode(encodedSeqNum)
}


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

