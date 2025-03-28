export const CHAT_TOPIC = 'universal-connectivity'
export const CHAT_FILE_TOPIC = 'universal-connectivity-nodejs-file'
export const PUBSUB_PEER_DISCOVERY = 'universal-connectivity-nodejs-peer-discovery'
export const FILE_EXCHANGE_PROTOCOL = '/universal-connectivity-nodejs-file/1'
export const DIRECT_MESSAGE_PROTOCOL = '/universal-connectivity-nodejs/dm/1.0.0'

export const CIRCUIT_RELAY_CODE = 291

export const MIME_TEXT_PLAIN = 'text/plain'

// 👇 App specific dedicated bootstrap PeerIDs
// Their multiaddrs are ephemeral so peer routing is used to resolve multiaddr
export const WEBTRANSPORT_BOOTSTRAP_PEER_ID = '12D3KooWH7MdJvo6L1ZvBmr9mgg5fZPCzQNG7UKKduxRqwiNDX6E'

export const BOOTSTRAP_PEER_IDS = [WEBTRANSPORT_BOOTSTRAP_PEER_ID]
