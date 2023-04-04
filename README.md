# Universal Connectivity

This is a chat app demontrating libp2p's super powers in establishing connectivity between multiple runtimes and languages.

- Uses the [**GossipSub**](https://docs.libp2p.io/concepts/pubsub/overview/) PubSub protocol for decentralized messaging
- The [chat frontend](./packages/frontend) is a Next.js app that uses [**js-libp2p**](https://github.com/libp2p/js-libp2p)
- The [go chat daemon](./go-peer) uses go-libp2p
