# Universal Connectivity

Realtime highly decentralised chat app.

![libp2p topology](libp2p-hero.svg)

Showcasing [libp2p](https://libp2p.io/)'s superpowers in establishing ubiquitous peer-to-peer [connectivity](https://connectivity.libp2p.io/) in modern programming languages (Go, Rust, TypeScript) and runtimes (Web, native binary).

On top of this strong foundation, it layers a GossipSub: A Secure PubSub Protocol for Unstructured Decentralised P2P Overlays. By analogy, an event broker with distributed brokering, or a distributed PubSub protocol.

This is the gossip event protocol that powers Filecoin and Post-Merge Ethereum.

Some of the cool and cutting-edge [transport protocols](https://connectivity.libp2p.io/) used by this app are:

- WebTransport
- WebRTC
- QUIC
- TCP

## Packages

| Packge                             | Description                                      | WebTransport | WebRTC | QUIC | TCP |
| :--------------------------------- | :----------------------------------------------- | ------------ | ------ | ---- | --- |
| [`frontend`](./packages/frontend/) | Next.js based browser UI of the chat app         | ✅           | ✅     | ❌   | ❌  |
| [`go-peer`](./go-peer/)            | Chat peer implemented in Go                      | ✅           | ❌     | ✅   | ✅  |
| [`rust-peer`](./rust-peer/)        | Chat peer implemented in Rust                    | ❌           | ✅     | ✅   | ❌  |
| [`node`](./packages/node/)         | Chat peer implemented with TypeScript in node.js | ❌           | ❌     | ❌   | ✅  |

✅ - Protocol supported
❌ - Protocol not supported

- Uses the [**GossipSub**](https://docs.libp2p.io/concepts/pubsub/overview/) PubSub protocol for decentralised messaging

## Connecting to a peer

There are two ways to connect to a peer:
- With a PeerID using peer routing (adds a step to resolve the multiaddr for the PeerID), using the IPFS/Libp2p DHT, e.g. `12D3KooWLMySi3eEWscUnKmMCYRSXL3obYJ4KNimpShJK6shUy2M`
- With a multiaddr directly (skips the peer routing step), e.g. `/ip4/127.0.0.1/udp/64434/webrtc/certhash/uEiA_tkndZQWf7jyFqgCiwH_CqsS7FTWFTb6Px8MPxxT9gQ/p2p/12D3KooWLMySi3eEWscUnKmMCYRSXL3obYJ4KNimpShJK6shUy2M`

[8-minute project setup & demo video](https://share.descript.com/view/wYYLohdYx5X)
git
### Using a multiaddr

Load the UI, and enter the multiaddr into the UI. Ensure that it includes the peerID, e.g.`/ip4/192.168.178.21/udp/61838/quic-v1/webtransport/certhash/uEiCQCALYac4V3LJ2ourLdauXOswIXpIuJ_JNT-8Wavmxyw/certhash/uEiCdYghq5FlXGkVONQXT07CteA16BDyMPI23-0GjA9Ej_w/p2p/12D3KooWF7ovRNBKPxERf6GtUbFdiqJsQviKUb7Z8a2Uuuo6MrDX`


## Getting started: frontend

The project uses [npm workspaces](https://docs.npmjs.com/cli/v7/using-npm/workspaces).


### 1. Install dependencies

Run npm install from the root of the repo:

```
npm i
```

### 2. Start Next.js dev server

Enter the frontend folder, start the dev server

```
cd packages/frontend
npm run dev
```

## Getting started: Rust

### 1. Start peer

```
cd rust-peer
cargo run
```

You should see the multiaddr of the peer once its loaded, e.g.

```
Listen address: "/ip4/127.0.0.1/udp/49350/webrtc/certhash/uEiAs1mQgRDVdSqMsQAuEnpMW0sSj6qc5jNvx2d0r3bQoiA/p2p/12D3KooWMzXTNGDLCKy6i6eAgJPMGCxuu7NJz33T9oC5kjByY27W
```


## Getting started: Go

### 1. Start peer

```
cd go-peer
go run .
```
