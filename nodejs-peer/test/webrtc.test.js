import puppeteer from 'puppeteer';
import { createLibp2p } from 'libp2p';
import { noise } from '@chainsafe/libp2p-noise';
import { webRTC, webRTCDirect } from '@libp2p/webrtc';
import { circuitRelayTransport } from '@libp2p/circuit-relay-v2';
import { identify } from '@libp2p/identify';
import { gossipsub } from '@chainsafe/libp2p-gossipsub';
import { yamux } from '@chainsafe/libp2p-yamux';
import { mdns } from '@libp2p/mdns';
import { pubsubPeerDiscovery } from '@libp2p/pubsub-peer-discovery';
import { ping } from '@libp2p/ping';
import { webTransport } from '@libp2p/webtransport';
import {tcp} from '@libp2p/tcp';
import {webSockets} from '@libp2p/websockets';

let browser, page, node;

beforeAll(async () => {
  node = await createLibp2p({
    addresses: {
      listen: [
        '/ip4/0.0.0.0/tcp/0',
        '/ip4/0.0.0.0/tcp/0/ws',
        '/webrtc',
        '/webrtc-direct',
      ],
    },
    transports: [
      tcp(),
      webSockets(),
      webRTC(),
      webRTCDirect(),
      webTransport(),
      circuitRelayTransport({ discoverRelays: 1 }),
    ],
    connectionEncrypters: [noise()],
    streamMuxers: [yamux()],
    connectionGater: {
      denyDialMultiaddr: async () => false, // Allow all multiaddrs
    },
    peerDiscovery: [
      mdns(),
      pubsubPeerDiscovery({ interval: 10_000, topics: ['libp2p-discovery'], listenOnly: false }),
    ],
    services: {
      pubsub: gossipsub(),
      identify: identify(),
      ping: ping(),
    },
  });

  await node.start();

  // const nodeAddr = '/ip4/172.25.240.1/udp/57282/webrtc-direct/certhash/uEiAdl46vLn4Cm_mNDWsmG2mp1aheK1VJkrloT0zjTMdjQA/p2p/12D3KooWRQf2JNXjgqjydvEt51HzPVuSYVrz7NJzGF2bo1LyQ6uK'
  
  //ensure multiaddrs are available
  let retries = 5;
  while (node.getMultiaddrs().length === 0 && retries > 0) {
    console.warn(`⚠️ No listening addresses found. Retrying in 3 seconds... (Attempts left: ${retries})`);
    await new Promise((resolve) => setTimeout(resolve, 3000));
    retries--;
  }

  const nodeMultiaddrs = node.getMultiaddrs();
  if (nodeMultiaddrs.length === 0) {
    throw new Error('❌ No multiaddrs found for Node.js peer');
  }

  console.log(`🚀 Node started at:`, nodeMultiaddrs.map((addr) => addr.toString()));

  browser = await puppeteer.launch({ headless: true });
  page = await browser.newPage();

  //Inject libp2p script into sandboxed-browser-env
  await page.addScriptTag({
    url: 'https://cdn.jsdelivr.net/npm/libp2p@latest/dist/index.min.js',
  });
});

afterAll(async () => {
  if (node) await node.stop();
  if (browser) await browser.close();
});

test('Browser WebRTC peer should connect to Node.js peer', async () => {
  const nodeMultiaddrs = node.getMultiaddrs();
  if (nodeMultiaddrs.length === 0) {
    throw new Error('❌ No multiaddrs found for Node.js peer');
  }

  const nodeMultiaddr = nodeMultiaddrs[0].toString();
  console.log(`📡 Node Multiaddr: ${nodeMultiaddr}`);

  await page.evaluate(async (nodeMultiaddr) => {
    if(typeof window === 'undefined' || window.libp2p === undefined) {
      return 'window not found!';
    } 
     const { createLibp2p, noise, yamux, webRTC, webRTCDirect, circuitRelayTransport, identify, multiaddr } = window.libp2p;

    const browserPeer = await createLibp2p({
      addresses: { listen: ['/webrtc'] },
      transports: [
        webRTC(),
        webRTCDirect(),
        circuitRelayTransport({ discoverRelays: 1 }),
      ],
      connectionEncryption: [noise()],
      streamMuxers: [yamux()],
      services: { identify: identify() },
    });

    await browserPeer.start();

    let retries = 5;
    while (browserPeer.getMultiaddrs().length === 0 && retries > 0) {
      console.warn(`⚠️ No listening addresses for browser peer. Retrying in 3 seconds... (Attempts left: ${retries})`);
      await new Promise((resolve) => setTimeout(resolve, 3000));
      retries--;
    }

    const browserMultiaddrs = browserPeer.getMultiaddrs();
    if (browserMultiaddrs.length === 0) {
      throw new Error('❌ No multiaddrs found for Browser peer');
    }

    console.log(`🚀 Browser peer started at:`, browserMultiaddrs.map((addr) => addr.toString()));

    const conn = await browserPeer.dial(multiaddr(nodeMultiaddr));
    console.log(`✅ Browser connected to ${conn.remotePeer.toString()}`);

  }, nodeMultiaddr);
}, 60000);




// import puppeteer from 'puppeteer';



// let browser, page, node;

// beforeAll(async () => {
//   node = 

//   await node.start();

//   // ✅ Retry logic to wait for multiaddrs
//   let retries = 5;
//   while (node.getMultiaddrs().length === 0 && retries > 0) {
//     console.warn(`⚠️ No listening addresses found. Retrying in 3 seconds... (Attempts left: ${retries})`);
//     await new Promise((resolve) => setTimeout(resolve, 3000));
//     retries--;
//   }

//   const nodeMultiaddrs = node.getMultiaddrs();
//   if (nodeMultiaddrs.length === 0) {
//     throw new Error('❌ No multiaddrs found for Node.js peer');
//   }

//   console.log(`🚀 Node started at:`, nodeMultiaddrs.map((addr) => addr.toString()));

//   browser = await puppeteer.launch({ headless: true });
//   page = await browser.newPage();
// });

// afterAll(async () => {
//   if(node) {
//     await node.stop();
//   }
//     if(browser) {
//         await browser.close();
//     }
// });

// test('Browser WebRTC peer should connect to Node.js peer', async () => {
//   const nodeMultiaddrs = node.getMultiaddrs();
//   if (nodeMultiaddrs.length === 0) {
//     throw new Error('❌ No multiaddrs found for Node.js peer');
//   }

//   const nodeMultiaddr = nodeMultiaddrs[0].toString();
//   console.log(`📡 Node Multiaddr: ${nodeMultiaddr}`);

//   await page.evaluate(async (nodeMultiaddr) => {
//     const { createLibp2p } = await import('libp2p');
//     const { noise } = await import('@chainsafe/libp2p-noise');
//     const {yamux}= await import('@chainsafe/libp2p-yamux');
//     const { webRTC, webRTCDirect } = await import('@libp2p/webrtc');
//     const { circuitRelayTransport } = await import('@libp2p/circuit-relay-v2');
//     const { identify } = await import('@libp2p/identify');
//     const { multiaddr } = await import('@multiformats/multiaddr');

//     const browserPeer = await createLibp2p({
//       addresses: { listen: ['/webrtc'] },
//       transports: [
//         webRTC({ rtcConfiguration: { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] } }), // ✅ STUN for NAT traversal
//         webRTCDirect(),
//         circuitRelayTransport({ discoverRelays: 1 }),
//       ],
//       connectionEncryption: [noise()],
//       streamMuxers: [yamux()],
//       services: { identify: identify() },
//     });

//     await browserPeer.start();

//     let retries = 5;
//     while (browserPeer.getMultiaddrs().length === 0 && retries > 0) {
//       console.warn(`⚠️ No listening addresses for browser peer. Retrying in 3 seconds... (Attempts left: ${retries})`);
//       await new Promise((resolve) => setTimeout(resolve, 3000));
//       retries--;
//     }

//     const browserMultiaddrs = browserPeer.getMultiaddrs();
//     if (browserMultiaddrs.length === 0) {
//       throw new Error('❌ No multiaddrs found for Browser peer');
//     }

//     console.log(`🚀 Browser peer started at:`, browserMultiaddrs.map((addr) => addr.toString()));

//     const conn = await browserPeer.dial(multiaddr(nodeMultiaddr));
//     console.log(`✅ Browser connected to ${conn.remotePeer.toString()}`);
//   }, nodeMultiaddr);
// }, 60000);



