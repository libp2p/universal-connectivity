import { createLibp2p } from "libp2p";
import { webRTC } from "@libp2p/webrtc";
import { webSockets } from "@libp2p/websockets";
import { tcp } from "@libp2p/tcp";
import { noise } from "@chainsafe/libp2p-noise";
import { circuitRelayTransport } from "@libp2p/circuit-relay-v2";
import { identify, identifyPush } from "@libp2p/identify";
import { dcutr } from "@libp2p/dcutr";
import { autoNAT } from "@libp2p/autonat";
import { yamux } from "@chainsafe/libp2p-yamux";
import { pubsubPeerDiscovery } from "@libp2p/pubsub-peer-discovery";
import { gossipsub } from "@chainsafe/libp2p-gossipsub";
import { CHAT_FILE_TOPIC, CHAT_TOPIC, PUBSUB_PEER_DISCOVERY } from "./constants.js";
import { kadDHT } from "@libp2p/kad-dht";
import { fromString as uint8ArrayFromString } from 'uint8arrays/from-string';
import { toString as uint8ArrayToString } from 'uint8arrays/to-string';
import { sha256 } from 'multiformats/hashes/sha2'; 
import { stdinToStream, streamToConsole } from './stream.js';

// Define the universal connectivity protocol constant
const UNIVERSAL_PROTOCOL = '/universal/1.0.0';

export async function createNode() {
  const node = await createLibp2p({
    addresses: {
      listen: [
        "/ip4/0.0.0.0/tcp/0/ws",
        "/ip4/0.0.0.0/tcp/0",
        '/webrtc',
        '/webrtc-direct',
      ],
    },
    transports: [
      webSockets(),
      tcp(),
      webRTC(),
      circuitRelayTransport({ discoverRelays: 1 })
    ],
    connectionEncrypters: [noise()],
    connectionManager: {
      maxConnections: 100,
      minConnections: 5,
      autoDialInterval: 30000,
      dialTimeout: 30000,
    },
    connectionGater: {
      denyDialMultiaddr: async ({ multiaddr }) => false,
    },
    streamMuxers: [yamux()],
    services: {
      pubsub: gossipsub({
        allowPublishToZeroTopicPeers: true,
        msgIdFn: msgIdFnStrictNoSign,
        ignoreDuplicatePublishError: true,
      }),
      identify: identify(),
      identifyPush: identifyPush(),
      dcutr: dcutr(),
      kadDHT: kadDHT(),
      autoNAT: autoNAT({
        protocolPrefix: "libp2p",
        startupDelay: 5000,
        refreshInterval: 60000,
      }),
    },
    peerDiscovery: [
      pubsubPeerDiscovery({
        interval: 30000,
        topics: [PUBSUB_PEER_DISCOVERY],
        listenOnly: false,
      }),
    ],
  });
  return node;
}

export async function msgIdFnStrictNoSign(msg) {
  const enc = new TextEncoder();
  const encodedSeqNum = enc.encode(msg.sequenceNumber.toString());
  return await sha256.encode(encodedSeqNum);
}

/**
 * Helper to dial a target multiaddr using the specified protocol.
 * Sets up interactive pipes for stdin and stdout.
 */
async function robustDial(sourceNode, targetMultiaddr, protocol = UNIVERSAL_PROTOCOL) {
  try {
    console.log(`Attempting to dial ${targetMultiaddr} using protocol ${protocol}`);
    const stream = await sourceNode.dialProtocol(targetMultiaddr, protocol);
    console.log(`Successfully dialed ${targetMultiaddr} with protocol ${protocol}`);
    // Set up interactive communication
    stdinToStream(stream);
    streamToConsole(stream);
    return stream;
  } catch (error) {
    console.error(`Failed to dial ${targetMultiaddr} using protocol ${protocol}: ${error.message}`);
    throw error;
  }
}

async function main() {
  // Create two nodes concurrently for testing purposes.
  const [node1, node2] = await Promise.all([createNode(), createNode()]);

  console.log(`Node1 ID: ${node1.peerId.toString()}`);
  node1.getMultiaddrs().forEach(addr => console.log(`Node1 listening on: ${addr.toString()}`));

  console.log(`Node2 ID: ${node2.peerId.toString()}`);
  node2.getMultiaddrs().forEach(addr => console.log(`Node2 listening on: ${addr.toString()}`));

  // // Setup universal protocol handler on node2.
  node2.handle(UNIVERSAL_PROTOCOL, async ({ stream, connection }) => {
    console.log(`Node2 received connection on ${UNIVERSAL_PROTOCOL} from ${connection.remotePeer.toString()}`);
    try {
      // Establish interactive communication.
      stdinToStream(stream);
      streamToConsole(stream);
    } catch (err) {
      console.log('Error in universal protocol handler on node2:', err.message);
    }
  });

  // Directly dial node2 from node1 using one of node2's multiaddrs.
  const targetAddr = node2.getMultiaddrs()[0];
  if (targetAddr) {
    await robustDial(node1, targetAddr, UNIVERSAL_PROTOCOL);
  } else {
    console.warn('No multiaddr found for node2');
  }

  // Log new connections on node1.
  node1.addEventListener('connection:open', (evt) => {
    try {
      const conn = evt.detail;
      console.log(`Node1: New connection opened from peer ${conn.remotePeer}`);
      console.log('Connection details:', conn);
    } catch (err) {
      console.log('Error in connection:open listener on node1:', err.message);
    }
  });

  // When a peer is discovered, attempt to dial using the universal protocol.
  node2.addEventListener('peer:discovery', async (evt) => {
    console.info('Node1 discovered peer:', evt.detail);
    const discoveredMultiaddrs = evt.detail.multiaddrs;
    if (discoveredMultiaddrs && discoveredMultiaddrs.length > 0) {
      try {
        await robustDial(node1, discoveredMultiaddrs, UNIVERSAL_PROTOCOL);
      } catch (error) {
        console.log('Error dialing discovered peer:', error.message);
      }
    }
  });

  // Setup pubsub subscriptions and logging.
  node1.services.pubsub.subscribe(CHAT_TOPIC);
  node1.services.pubsub.addEventListener('message', (evt) => {
    try{
    console.log(`Node1 received on topic ${evt.detail.topic}: ${uint8ArrayToString(evt.detail.data)}`);
  } catch (err) {
    console.error('Error decoding received message on Node1:', err.message);
  }
  });

  node2.services.pubsub.subscribe(CHAT_TOPIC);
  node2.services.pubsub.addEventListener('message', (evt) => {
    try{
      // console.log('Raw message bytes:', evt.detail.data);
    console.log(`Node2 received on topic ${evt.detail.topic}: ${uint8ArrayToString(evt.detail.data)}`);
  } catch (err) {
    console.error('Error decoding received message on Node2:', err.message);
  }
  });

  // For testing: Node2 periodically publishes messages on several topics.
  setInterval(() => {
    node2.services.pubsub.publish(CHAT_TOPIC, uint8ArrayFromString('Hello Go & Rust!'))
        .catch(err => console.log(`Error publishing to ${CHAT_TOPIC}:`, err.message));
    }, 3000);

  console.log('Nodes are running and ready for robust dialing and interactions.');
}

main().catch(err => {
  console.log('Main execution error:', err.message);
  process.exit(1);
});

export class NATManager {
  constructor(node) {
    node.addEventListener('self:nat:status', (evt) => {
      console.log('NAT Status:', evt.detail)
      if(evt.detail === 'UNSUPPORTED') {
        console.log('Enabling circuit relay as fallback')
        node.configure(circuitRelayTransport({ discoverRelays: 2 }))
      }
    })
  }
}