import {
  createDelegatedRoutingV1HttpApiClient,
} from '@helia/delegated-routing-v1-http-api-client'
import { createLibp2p } from 'libp2p'
import { identify } from '@libp2p/identify'
import { noise } from '@chainsafe/libp2p-noise'
import { yamux } from '@chainsafe/libp2p-yamux'
import { sha256 } from 'multiformats/hashes/sha2'
import type { Message, SignedMessage } from '@libp2p/interface'
import { gossipsub } from '@chainsafe/libp2p-gossipsub'
import { webSockets } from '@libp2p/websockets'
import { webRTC, webRTCDirect } from '@libp2p/webrtc'
import { circuitRelayTransport } from '@libp2p/circuit-relay-v2'
import { pubsubPeerDiscovery } from '@libp2p/pubsub-peer-discovery'
import { ping } from '@libp2p/ping'
import { BOOTSTRAP_PEER_IDS, CHAT_TOPIC, PUBSUB_PEER_DISCOVERY } from '../constants.js'
import { directMessage } from './direct-message.js'
import { quic } from '@chainsafe/libp2p-quic'
import { tcp } from '@libp2p/tcp'
import { peerIdFromString } from '@libp2p/peer-id'

// message IDs are used to dedupe inbound messages
// every agent in network should use the same message id function
// messages could be perceived as duplicate if this isn't added (as opposed to
// rust peer which has unique message ids)
export async function msgIdFnStrictNoSign(msg: Message): Promise<Uint8Array> {
  var enc = new TextEncoder()

  const signedMessage = msg as SignedMessage
  const encodedSeqNum = enc.encode(signedMessage.sequenceNumber.toString())
  return await sha256.encode(encodedSeqNum)
}

export async function startLibp2p () {
  const delegatedClient = createDelegatedRoutingV1HttpApiClient('https://delegated-ipfs.dev')
  const node = await createLibp2p({
    addresses: {
      listen: [
        '/webrtc-direct',
        '/ip4/0.0.0.0/tcp/0',
        '/ip4/0.0.0.0/udp/0/quic-v1'
      ]
    },
    transports: [
      webSockets(),
      webRTC(),
      webRTCDirect(),
      circuitRelayTransport(),
      quic(),
      tcp()
    ],
    connectionEncrypters: [noise()],
    streamMuxers: [yamux()],
    connectionGater: {
      denyDialMultiaddr: async () => false
    },
    peerDiscovery: [
      pubsubPeerDiscovery({
        interval: 10_000,
        topics: [PUBSUB_PEER_DISCOVERY],
        listenOnly: false
      })
    ],
    services: {
      pubsub: gossipsub({
        allowPublishToZeroTopicPeers: true,
        msgIdFn: msgIdFnStrictNoSign,
        ignoreDuplicatePublishError: true,
      }),
      // Delegated routing helps us discover the ephemeral multiaddrs of the
      // dedicated go and rust bootstrap peers
      // This relies on the public delegated routing endpoint
      // See https://docs.ipfs.tech/concepts/public-utilities/#delegated-routing
      delegatedRouting: () => delegatedClient,
      identify: identify(),
      // Custom protocol for direct messaging
      directMessage: directMessage(),
      ping: ping()
    }
  })

  // subscribe to incoming chat messages
  node.services.pubsub.subscribe(CHAT_TOPIC)

  // find and dial the bootstrap peers
  Promise.resolve().then(async () => {
    for (const id of BOOTSTRAP_PEER_IDS) {
      const peerId = peerIdFromString(id)
      const peer = await node.peerRouting.findPeer(peerId, {
        useCache: false
      })
      await node.dial(peer.id)
    }
  })
    .catch(err => {
      console.error('bootstrap error', err)
    })

  // try to dial topic peers - this is a hack to make them appear in the chat
  // peer list.
  //
  // Note that we do not need a connection to a peer to receive its messages
  // since they will be forwarded on by mesh peers. For more info see the spec:
  // https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/README.md
  node.services.pubsub.addEventListener('message', (evt) => {
    if (evt.detail.topic === CHAT_TOPIC && evt.detail.type === 'signed') {
      node.dial(evt.detail.from)
        .catch(() => {})
    }
  })

  return node
}
