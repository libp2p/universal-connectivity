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



## Getting started – frontend and node

The project uses [npm workspaces](https://docs.npmjs.com/cli/v7/using-npm/workspaces).


### 1. Install dependencies

Run npm install from the root of the repo:

```
npm i
```

### 2. Start dev server

Enter the frontend folder, start the dev server

```
cd packages/frontend
npm run dev
```
