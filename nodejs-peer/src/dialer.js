import { createLibp2p } from "libp2p";
import { noise } from "@chainsafe/libp2p-noise";
import { yamux } from "@chainsafe/libp2p-yamux";
import { tcp } from "@libp2p/tcp";
import { webSockets } from "@libp2p/websockets";
import { webRTC, webRTCDirect } from "@libp2p/webrtc";
import { circuitRelayTransport } from "@libp2p/circuit-relay-v2";
import { identify } from "@libp2p/identify";
import { multiaddr } from "@multiformats/multiaddr";
import { pubsubPeerDiscovery } from "@libp2p/pubsub-peer-discovery";
import { ping } from "@libp2p/ping";
import { gossipsub } from "@chainsafe/libp2p-gossipsub";
import { PUBSUB_PEER_DISCOVERY } from "./constants.js";

const dialPeer = async (peerMultiaddr) => {
  const dialer = await createLibp2p({
    addresses: {
      listen: [
        "/ip4/0.0.0.0/tcp/0",
        "/ip4/0.0.0.0/tcp/0/ws",
        "/webrtc",
        "/webrtc-direct",
      ],
    },
    transports: [
      tcp(),
      webSockets(),
      webRTC(),
      webRTCDirect(),
      circuitRelayTransport({ discoverRelays: 1 }),
    ],
    connectionEncrypters: [noise()],
    streamMuxers: [yamux()],
    services: {
      identify: identify(),
      ping: ping(),
      pubsub: gossipsub(),
    },
    peerDiscovery: [
      pubsubPeerDiscovery({
        interval: 60000,
        topics: [PUBSUB_PEER_DISCOVERY],
        listenOnly: false,
      }),
    ],
  });

  console.log("Dialer started, listening on:");
  dialer.getMultiaddrs().forEach((addr) => console.log(addr.toString()));

  try {
    console.log(`🔄 Dialing peer: ${peerMultiaddr}`);
    const conn = await dialer.dial(multiaddr(peerMultiaddr));
    console.log(`✅ Successfully dialed ${conn.remotePeer.toString()}`);
  } catch (err) {
    console.error(`❌ Dialing failed: ${err.message}`);
  }
};

const peerMultiaddr = process.argv[2];
if (!peerMultiaddr) {
  console.error("❌ Please provide a peer multiaddr to dial.");
  process.exit(1);
}

dialPeer(peerMultiaddr).catch((err) =>
  console.log("❌ Unexpected error:", err.message)
);
