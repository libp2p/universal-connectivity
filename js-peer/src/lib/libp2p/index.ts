import { createLibp2p, Libp2p } from 'libp2p'
import { identify } from '@libp2p/identify'
import { noise } from '@chainsafe/libp2p-noise'
import { yamux } from '@chainsafe/libp2p-yamux'
import { bootstrap } from '@libp2p/bootstrap'
import { kadDHT } from '@libp2p/kad-dht'
import { dcutr } from '@libp2p/dcutr'
import { pubsubPeerDiscovery } from '@libp2p/pubsub-peer-discovery'
import {
  Multiaddr,
} from '@multiformats/multiaddr'
import { sha256 } from 'multiformats/hashes/sha2'
import type { Message, SignedMessage } from '@libp2p/interface'
import { gossipsub } from '@chainsafe/libp2p-gossipsub'
import { webSockets } from '@libp2p/websockets'
import { webTransport } from '@libp2p/webtransport'
import { webRTC, webRTCDirect } from '@libp2p/webrtc'
import { CHAT_FILE_TOPIC, CHAT_TOPIC, WEBRTC_BOOTSTRAP_NODE, WEBTRANSPORT_BOOTSTRAP_NODE } from '../constants/'
import * as filters from "@libp2p/websockets/filters"
import { circuitRelayTransport } from '@libp2p/circuit-relay-v2'

export async function startLibp2p() {
  // enable verbose logging in browser console to view debug logs
  // localStorage.debug = 'libp2p*,-*:trace'

  // application-specific data lives in the datastore

  const libp2p = await createLibp2p({
    addresses: {
      listen: [
        '/webrtc'
      ]
    },
    transports: [
      webTransport(),
      webSockets({
        // this allows non-secure WebSocket connections, e.g. to local network
        filter: filters.all,
      }),
      webRTC({
        rtcConfiguration: {
          iceServers: [{
            urls: [
              'stun:stun.l.google.com:19302',
              'stun:global.stun.twilio.com:3478'
            ]
          }]
        }
      }),
      webRTCDirect(),
      circuitRelayTransport({
        discoverRelays: 1,
      })
    ],
    connectionManager: {
      maxConnections: 10,
      minConnections: 5
    },
    connectionEncryption: [noise()],
    streamMuxers: [yamux()],
    connectionGater: {
      denyDialMultiaddr: async () => false,
    },
    peerDiscovery: [
      bootstrap({
        list: [
          '/ip4/161.35.148.108/udp/1970/quic-v1/webtransport/certhash/uEiBrr7E3WmC1omWyLEEPBlSkhdJxXp7eJSmcsdEor0uv2w/certhash/uEiAo-TevMGFzO1LPlUSmZvRquvCi8p4IReI0JpNnL4kLNQ/p2p/12D3KooWP6cwye9umPLg1T6fs7vUfLMShbKNoZmLb6iswBfMyfAM'
          // WEBRTC_BOOTSTRAP_NODE,
          // WEBTRANSPORT_BOOTSTRAP_NODE,
        ],
      }),
      pubsubPeerDiscovery({
        interval: 5000,
        listenOnly: false,
        topics: [`${CHAT_TOPIC}._peer-discovery._p2p._pubsub`],
      }),

    ],
    services: {
      pubsub: gossipsub({
        emitSelf: false,
        allowPublishToZeroTopicPeers: true,
        msgIdFn: msgIdFnStrictNoSign,
        ignoreDuplicatePublishError: true,
        tagMeshPeers: true,
        doPX: true,

      }),
      dht: kadDHT({
        protocol: "/universal-connectivity/kad/1.0.0",
        maxInboundStreams: 5000,
        maxOutboundStreams: 5000,
        clientMode: true,
      }),
      identify: identify(),
      dcutr: dcutr(),
    },
  })

  libp2p.services.pubsub.subscribe(CHAT_TOPIC)
  libp2p.services.pubsub.subscribe(CHAT_FILE_TOPIC)

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

