import {
  createDelegatedRoutingV1HttpApiClient,
  DelegatedRoutingV1HttpApiClient,
} from "@helia/delegated-routing-v1-http-api-client";
import { createLibp2p } from "libp2p";
import { Identify, identify } from "@libp2p/identify";
import { peerIdFromString } from "@libp2p/peer-id";
import { noise } from "@chainsafe/libp2p-noise";
import { yamux } from "@chainsafe/libp2p-yamux";
import { bootstrap } from "@libp2p/bootstrap";
import { Multiaddr } from "@multiformats/multiaddr";
import { sha256 } from "multiformats/hashes/sha2";
import type {
  Connection,
  Message,
  SignedMessage,
  PeerId,
  Libp2p,
  PeerInfo,
  PeerDiscoveryEvents,
} from "@libp2p/interface";
import { gossipsub } from "@chainsafe/libp2p-gossipsub";
import { webSockets } from "@libp2p/websockets";
import { webTransport } from "@libp2p/webtransport";
import { webRTC, webRTCDirect } from "@libp2p/webrtc";
import { circuitRelayTransport } from "@libp2p/circuit-relay-v2";
import { pubsubPeerDiscovery } from "@libp2p/pubsub-peer-discovery";
import { ping } from "@libp2p/ping";
import {
  BOOTSTRAP_PEER_IDS,
  CHAT_FILE_TOPIC,
  CHAT_TOPIC,
  PUBSUB_PEER_DISCOVERY,
} from "./constants";
import first from "it-first";
import { forComponent, enable } from "./logger";
import { directMessage } from "./direct-message";
import type { Libp2pType } from "@/context/ctx";
import { kadDHT } from "@libp2p/kad-dht";
import type {
  QueryEvent,
  PeerResponseEvent,
  EventTypes,
} from "@libp2p/kad-dht";

const log = forComponent("libp2p");

export async function startLibp2p(): Promise<Libp2pType> {
  // enable verbose logging in browser console to view debug logs
  enable("ui*,libp2p*,-libp2p:connection-manager*,-*:trace");

  const delegatedClient = createDelegatedRoutingV1HttpApiClient(
    "https://delegated-ipfs.dev"
  );

  const { bootstrapAddrs, relayListenAddrs } = await getBootstrapMultiaddrs(
    delegatedClient
  );
  log(
    "starting libp2p with bootstrapAddrs %o and relayListenAddrs: %o",
    bootstrapAddrs,
    relayListenAddrs
  );

  let libp2p: Libp2pType;

  libp2p = await createLibp2p({
    addresses: {
      listen: [
        // 👇 Listen for webRTC connection
        "/webrtc",
        ...relayListenAddrs,
      ],
    },
    transports: [
      webTransport(),
      webSockets(),
      webRTC(),
      // 👇 Required to estalbish connections with peers supporting WebRTC-direct, e.g. the Rust-peer
      webRTCDirect(),
      // 👇 Required to create circuit relay reservations in order to hole punch browser-to-browser WebRTC connections
      circuitRelayTransport(),
    ],
    connectionEncrypters: [noise()],
    streamMuxers: [yamux()],
    connectionGater: {
      denyDialMultiaddr: async () => false,
    },
    peerDiscovery: [
      pubsubPeerDiscovery({
        interval: 10_000,
        topics: [PUBSUB_PEER_DISCOVERY],
        listenOnly: false,
      }),
      bootstrap({
        // The app-specific bootstrappers that use WebTransport and WebRTC-direct and have ephemeral multiadrrs
        // that are resolved above using the delegated routing API
        list: [
          `${bootstrapAddrs}`,
          "/ip6/2604:1380:4642:6600::3/udp/9095/quic-v1/webtransport/certhash/uEiAFmismVS4uGGz9zF8yLRC10wtqPciwcBD1BuAch4sX3A/certhash/uEiBEvL3ao0UqfMSkj2JCOvjG_4BEiiEnjFr7qmDPALgG5Q",
          "/ip6/2604:1380:4642:6600::3/udp/9095/quic-v1",
          "/ip4/147.28.186.157/udp/9095/webrtc-direct/certhash/uEiC6yY8kGKhTw9gr74_eDLWf08PNyAiSKgs22JHc_rD8qw",
          "/ip4/147.28.186.157/udp/9095/quic-v1",
          "/ip4/147.28.186.157/udp/9095/quic-v1/webtransport/certhash/uEiAFmismVS4uGGz9zF8yLRC10wtqPciwcBD1BuAch4sX3A/certhash/uEiBEvL3ao0UqfMSkj2JCOvjG_4BEiiEnjFr7qmDPALgG5Q",
        ],
      }),
    ],
    services: {
      pubsub: gossipsub({
        allowPublishToZeroTopicPeers: true,
        msgIdFn: msgIdFnStrictNoSign,
        ignoreDuplicatePublishError: true,
      }),
      // Delegated routing helps us discover the ephemeral multiaddrs of the dedicated go and rust bootstrap peers
      // This relies on the public delegated routing endpoint https://docs.ipfs.tech/concepts/public-utilities/#delegated-routing
      delegatedRouting: () => delegatedClient,
      identify: identify(),
      // Custom protocol for direct messaging
      directMessage: directMessage(),
      ping: ping(),
      dht: kadDHT(),
    },
  });

  if (!libp2p) {
    throw new Error("Failed to create libp2p node");
  }

  libp2p.services.pubsub.subscribe(CHAT_TOPIC);
  libp2p.services.pubsub.subscribe(CHAT_FILE_TOPIC);

  libp2p.addEventListener("self:peer:update", ({ detail: { peer } }) => {
    const multiaddrs = peer.addresses.map(({ multiaddr }) => multiaddr);
    log(
      `changed multiaddrs: peer ${peer.id.toString()} multiaddrs: ${multiaddrs}`
    );
  });

  // 👇 explicitly dial peers discovered via pubsub
  libp2p.addEventListener("peer:discovery", (event) => {
    const { multiaddrs, id } = event.detail;
    let accioPeers = [];
    const peerId = id.toString();
    accioPeers.push(peerId);
    console.log("Discovered Peer:", peerId);
    if (libp2p.getConnections(id)?.length > 0) {
      log(`Already connected to peer %s. Will not try dialling`, id);

      return;
    }

    dialWebRTCMaddrs(libp2p, multiaddrs);
  });

  return libp2p;
}

export const findPeerById =
  (libp2p: Libp2pType) => async (peerIdStr: string) => {
    console.log(`🔍 Searching for PeerID: ${peerIdStr}`);
    try {
      const peerId = peerIdFromString(peerIdStr);

      // Step 1: Check if the peer is already known in the peerstore
      const knownPeer = await libp2p.peerStore.get(peerId);
      if (knownPeer?.addresses?.length) {
        console.log(
          `✅ Found peer in peerStore with ${knownPeer.addresses.length} addresses`
        );
        return knownPeer;
      }

      // Step 2: Find the peer using DHT lookup with retries
      let event: QueryEvent | undefined;
      let attempts = 0;
      while (attempts < 3 && !event) {
        console.log(`🔄 DHT lookup attempt ${attempts + 1}`);
        event = await first(libp2p.services.dht.findPeer(peerId));
        attempts++;
      }

      if (!event) {
        console.warn(`⚠️ No DHT response after ${attempts} attempts`);
        return null;
      }

      // Step 3: Handle DHT response
      if (event.name === "FINAL_PEER") {
        const peerData = event.peer;
        if (peerData && peerData.multiaddrs?.length > 0) {
          // Convert to PeerInfo format
          const peerInfo = {
            id: peerData.id,
            addresses: peerData.multiaddrs.map((maddr) => ({
              multiaddr: maddr,
              isCertified: true,
            })),
            protocols: [],
            metadata: new Map(),
            tags: new Map(),
          };
          console.log(
            `✅ Found peer via DHT with ${peerInfo.addresses.length} addresses`
          );
          return peerInfo;
        }
      }

      // Step 4: Handle PEER_RESPONSE as fallback
      if (event.name === "PEER_RESPONSE") {
        const peerEvent = event as PeerResponseEvent;
        if (peerEvent.closer?.[0]) {
          const closestPeer = peerEvent.closer[0];
          // Convert to PeerInfo format
          const peerInfo = {
            id: closestPeer.id,
            addresses: closestPeer.multiaddrs.map((maddr) => ({
              multiaddr: maddr,
              isCertified: true,
            })),
            protocols: [],
            metadata: new Map(),
            tags: new Map(),
          };
          console.log(
            `✅ Found closest peer via DHT with ${peerInfo.addresses.length} addresses`
          );
          return peerInfo;
        }
      }

      console.warn(`⚠️ No valid peer information found`);
      return null;
    } catch (error) {
      console.error(`❌ Peer lookup failed:`, error);
      return null;
    }
  };

/* Connect by peer-ID */
// export const findPeerById =  (libp2p: Libp2pType) => async (peerIdStr : string) =>  {
//   console.log(`🔍 Searching for PeerID`)
//   try {
//     const peerId = peerIdFromString(peerIdStr)
//     console.log(`🔍 Searching for PeerID: ${peerIdStr}`)
//     // Step 1: Check if the peer is already known in the peerstore
//     const knownPeer =await libp2p.peerStore.get(peerId)
//     if (knownPeer?.addresses?.length) {
//       console.log(`✅ Peer already known in peerStore: ${knownPeer.addresses.map(a => a.multiaddr.toString()).join(', ')}`)
//       return knownPeer
//     }

//      // Step 2: Find the peer using DHT lookup
//      let event: QueryEvent | undefined
//      let attempts = 0
//      while (attempts < 3 && !event) {
//        console.log(`🔄 Attempt ${attempts + 1}: Finding peer in DHT...`)
//        event = await first(libp2p.services.dht.findPeer(peerId))
//        attempts++
//      }

//      // Use first() to extract a valid result from AsyncIterable<QueryEvent>
//     //  const event: QueryEvent | undefined = await first(libp2p.services.dht.findPeer(peerId))

//     if (!event) {
//       console.warn(`⚠️ No response received for PeerID: ${peerIdStr} after ${attempts} attempts`)
//       return null
//     }

//     let peerInfo: PeerInfo | null = null

//     // Step 3: Handle FINAL_PEER event (preferred case)
//     if (event.name === 'FINAL_PEER') {
//       const peerEvent = event as unknown as PeerDiscoveryEvents
//       console.log("peerevent=", peerEvent);
//       const peerInfo = peerEvent?.peer.detail // Extract first available PeerInfo
//       console.log("peer info=", peerInfo)
//         if (peerInfo.multiaddrs.length > 0) {
//           console.log(`✅ Found Peer Multiaddrs: ${peerInfo.multiaddrs.map(ma => ma.toString()).join(', ')}`)
//           return peerInfo
//     }
//   }

//     // Step 4: Handle PEER_RESPONSE event (fallback)
//     if (!peerInfo && event.name === 'PEER_RESPONSE') {
//       const peerEvent = event as PeerResponseEvent
//       if (peerEvent.closer?.length > 0) {
//         peerInfo = peerEvent.closer[0] // Select the first available peer
//       }
//     }

//      // Step 5: If no multiaddrs are found, try fetching from peerStore again
//      if (peerInfo && !peerInfo.multiaddrs?.length) {
//       const storedPeer =await libp2p.peerStore.get(peerInfo.id)
//       if (storedPeer?.addresses?.length) {
//         console.log(`✅ Retrieved Peer Multiaddrs from PeerStore: ${storedPeer.addresses.map(a => a.multiaddr.toString()).join(', ')}`)
//         return storedPeer
//       }
//     }

//     // Step 6: If still no multiaddrs, try bootstrapped peers as a fallback
//     if (!peerInfo || !peerInfo.multiaddrs?.length) {
//       console.warn(`⚠️ Peer found but no multiaddrs available: ${peerIdStr}. Attempting bootstrap nodes...`)
//       return null
//     }
//     console.log(`✅ Found Peer Multiaddrs: ${peerInfo.multiaddrs.map(ma => ma.toString()).join(', ')}`)
//     return peerInfo

//     // Ensure event is of type 'FINAL_PEER' and contains peer info
//     // if (event.name === 'FINAL_PEER') {
//     //   const peerEvent = event as unknown as PeerResponseEvent
//     //   if (peerEvent.closer && peerEvent.closer.length > 0) {
//     //     const peerInfo = peerEvent.closer[0] // Extract first available PeerInfo
//     //     if (peerInfo.multiaddrs.length > 0) {
//     //       console.log(`✅ Found Peer Multiaddrs: ${peerInfo.multiaddrs.map(ma => ma.toString()).join(', ')}`)
//     //       return peerInfo
//     //     }
//     //   }
//     // }

//     // // If FINAL_PEER is missing, check closer peers
//     // if (event.name === 'PEER_RESPONSE') {
//     //   const peerEvent = event as PeerResponseEvent
//     //   if (peerEvent.closer && peerEvent.closer.length > 0) {
//     //     console.log(`✅ Found closer peers, selecting first available one`)
//     //     return peerEvent.closer[0] // Return first available peer
//     //   }
//     // }

//     // console.warn(`⚠️ Peer found but no multiaddrs available: ${peerIdStr}`)

//   } catch (error) {
//     console.error(`❌ Peer lookup failed: ${error instanceof Error ? error.message : error}`)
//     return null
//   }
// }

// message IDs are used to dedupe inbound messages
// every agent in network should use the same message id function

// messages could be perceived as duplicate if this isnt added (as opposed to rust peer which has unique message ids)
export async function msgIdFnStrictNoSign(msg: Message): Promise<Uint8Array> {
  var enc = new TextEncoder();

  const signedMessage = msg as SignedMessage;
  const encodedSeqNum = enc.encode(signedMessage.sequenceNumber.toString());
  return await sha256.encode(encodedSeqNum);
}

// Function which dials one maddr at a time to avoid establishing multiple connections to the same peer
async function dialWebRTCMaddrs(
  libp2p: Libp2p,
  multiaddrs: Multiaddr[]
): Promise<void> {
  // Filter webrtc (browser-to-browser) multiaddrs
  const webRTCMadrs = multiaddrs.filter((maddr) =>
    maddr.protoNames().includes("webrtc")
  );
  log(`dialling WebRTC multiaddrs: %o`, webRTCMadrs);

  for (const addr of webRTCMadrs) {
    try {
      log(`attempting to dial webrtc multiaddr: %o`, addr);
      await libp2p.dial(addr);
      return; // if we succeed dialing the peer, no need to try another address
    } catch (error) {
      log.error(`failed to dial webrtc multiaddr: %o`, addr);
    }
  }
}

export const connectToMultiaddr =
  (libp2p: Libp2p) => async (multiaddr: Multiaddr) => {
    log(`dialling: %a`, multiaddr);
    try {
      const conn = await libp2p.dial(multiaddr);
      log("connected to %p on %a", conn.remotePeer, conn.remoteAddr);
      return conn;
    } catch (e) {
      console.error(e);
      throw e;
    }
  };

// Function which resolves PeerIDs of rust/go bootstrap nodes to multiaddrs dialable from the browser
// Returns both the dialable multiaddrs in addition to the relay
async function getBootstrapMultiaddrs(
  client: DelegatedRoutingV1HttpApiClient
): Promise<BootstrapsMultiaddrs> {
  const peers = await Promise.all(
    BOOTSTRAP_PEER_IDS.map((peerId) =>
      first(client.getPeers(peerIdFromString(peerId)))
    )
  );

  const bootstrapAddrs = [];
  const relayListenAddrs = [];
  for (const p of peers) {
    if (p && p.Addrs.length > 0) {
      for (const maddr of p.Addrs) {
        const protos = maddr.protoNames();
        if (
          (protos.includes("webtransport") ||
            protos.includes("webrtc-direct")) &&
          protos.includes("certhash")
        ) {
          if (maddr.nodeAddress().address === "127.0.0.1") continue; // skip loopback
          bootstrapAddrs.push(maddr.toString());
          // console.log("Bootstrap Peers:", bootstrapAddrs)
          relayListenAddrs.push(getRelayListenAddr(maddr, p.ID));
        }
      }
    }
  }
  return { bootstrapAddrs, relayListenAddrs };
}

interface BootstrapsMultiaddrs {
  // Multiaddrs that are dialable from the browser
  bootstrapAddrs: string[];

  // multiaddr string representing the circuit relay v2 listen addr
  relayListenAddrs: string[];
}

// Constructs a multiaddr string representing the circuit relay v2 listen address for a relayed connection to the given peer.
const getRelayListenAddr = (maddr: Multiaddr, peer: PeerId): string =>
  `${maddr.toString()}/p2p/${peer.toString()}/p2p-circuit`;

export const getFormattedConnections = (connections: Connection[]) =>
  connections.map((conn) => ({
    peerId: conn.remotePeer,
    protocols: [...new Set(conn.remoteAddr.protoNames())],
  }));
