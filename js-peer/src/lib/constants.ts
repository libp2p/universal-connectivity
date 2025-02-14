export const CHAT_TOPIC = 'universal-connectivity'
export const CHAT_FILE_TOPIC = 'universal-connectivity-file'
export const PUBSUB_PEER_DISCOVERY = 'universal-connectivity-browser-peer-discovery'
export const FILE_EXCHANGE_PROTOCOL = '/universal-connectivity-file/1'
export const DIRECT_MESSAGE_PROTOCOL = '/universal-connectivity/dm/1.0.0'

export const CIRCUIT_RELAY_CODE = 290

export const MIME_TEXT_PLAIN = 'text/plain'

// 👇 App specific dedicated bootstrapper subscribed to the pubsub topic `universal-connectivity` for relaying messages
export const GO_MESSAGE_BOOTSTRAP_PEER_ID = '12D3KooWFhXabKDwALpzqMbto94sB7rvmZ6M28hs9Y9xSopDKwQr'
export const GO_BOOTSTRAPPER_MADDR = '/ip4/147.28.186.157/tcp/9095/tls/sni/147-28-186-157.k51qzi5uqu5did09qdbdg7jf0pydff1llcd6h4deiasuc7qyemy3v8bc1q1rlb.libp2p.direct/ws'


export const BOOTSTRAP_PEER_IDS = [GO_MESSAGE_BOOTSTRAP_PEER_ID]
