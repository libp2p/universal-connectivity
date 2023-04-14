import { createLibp2p } from 'libp2p'
import { noise } from '@chainsafe/libp2p-noise'
import { yamux } from '@chainsafe/libp2p-yamux'
import { bootstrap } from '@libp2p/bootstrap'
import { kadDHT } from '@libp2p/kad-dht'
import {
  multiaddr,
  Multiaddr,
} from '@multiformats/multiaddr'
import { sha256 } from 'multiformats/hashes/sha2'
import type { Message, SignedMessage } from '@libp2p/interface-pubsub'
import { gossipsub } from '@chainsafe/libp2p-gossipsub'
import { webSockets } from '@libp2p/websockets'
import { webTransport } from '@libp2p/webtransport'
import { webRTC, webRTCDirect } from '@libp2p/webrtc'
import { BOOTSTRAP_NODE, CHAT_TOPIC, CIRCUIT_RELAY_CODE } from './constants'
import * as filters from "@libp2p/websockets/filters"

// @ts-ignore
import { circuitRelayTransport, circuitRelayServer } from 'libp2p/circuit-relay'


export async function startLibp2p() {
  // localStorage.debug = 'libp2p*,-*:trace'
  // application-specific data lives in the datastore

  // libp2p is the networking layer that underpins Helia
  const libp2p = await createLibp2p({
    // set the inbound and outbound stream limits to these values
    // because we were seeing a lot of the default limits being hit
    dht: kadDHT({protocolPrefix: "/universal-connectivity", maxInboundStreams: 1000, maxOutboundStreams: 1000, clientMode: true}),
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
      discoverRelays: 10,
    }),],
    connectionEncryption: [noise()],
    connectionManager: {
      maxConnections: 100,
      minConnections: 1,
    },
    streamMuxers: [yamux()],
    peerDiscovery: [
      bootstrap({
        list: [
          // BOOTSTRAP_NODE,
          '/ip4/127.0.0.1/udp/9090/webrtc-direct/certhash/uEiBy_U1UNQ0IDvot_PKlQM_QeU3yx-zCAVaMxxVm2JxWBg/p2p/12D3KooWSFfVyasFDa4NBQMzTmzSQBehUV92Exs9dsGjr9DL5TS3',
        ],
      }),
    ],
    pubsub: gossipsub({
      allowPublishToZeroPeers: true,
      msgIdFn: msgIdFnStrictNoSign,
      ignoreDuplicatePublishError: true,
    }),
    identify: {
      // these are set because we were seeing a lot of identify and identify push
      // stream limits being hit
      maxPushOutgoingStreams: 1000,
      maxPushIncomingStreams: 1000,
      maxInboundStreams: 1000,
      maxOutboundStreams: 1000,
    },
    autonat: {
      startupDelay: 60 * 60 *24 * 1000,
    },
    // This allows the browser node to act as a relay
    // this is set because this seems to be the only
    // way to set the inbound and outbound hop stream limits
    // We were seeing the default limit of 64 being hit and resulting errors
    relay: circuitRelayServer({
        maxInboundHopStreams: 1000,
        maxOutboundHopStreams: 1000
    }),
  })

  libp2p.pubsub.subscribe(CHAT_TOPIC)

  libp2p.peerStore.addEventListener('change:multiaddrs', ({detail: {peerId, multiaddrs}}) => {

    console.log(`changed multiaddrs: peer ${peerId.toString()} multiaddrs: ${multiaddrs}`)
    setWebRTCRelayAddress(multiaddrs, libp2p.peerId.toString())
  })

  return libp2p
}

// message IDs are used to dedup inbound messages
// every agent in network should use the same message id function
// messages could be perceived as duplicate if this isnt added (as opposed to rust peer which has unique message ids)
export async function msgIdFnStrictNoSign(msg: Message): Promise<Uint8Array> {
  var enc = new TextEncoder();

  const signedMessage = msg as SignedMessage
  const encodedSeqNum = enc.encode(signedMessage.sequenceNumber.toString());
  return await sha256.encode(encodedSeqNum)
}


export const setWebRTCRelayAddress = (maddrs: Multiaddr[], peerId: string) => {
  maddrs.forEach((maddr) => {
    if (maddr.protoCodes().includes(CIRCUIT_RELAY_CODE)) {

      const webRTCrelayAddress = multiaddr(maddr.toString() + '/webrtc/p2p/' + peerId)

      console.log(`Listening on '${webRTCrelayAddress.toString()}'`)
    }
  })
}

