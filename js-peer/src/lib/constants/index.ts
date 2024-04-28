export const APP_PREFIX = 'universal-connectivity'

export const CHAT_TOPIC = APP_PREFIX
export const CHAT_FILE_TOPIC = `${APP_PREFIX}-file`
export const PUBSUB_PEER_DISCOVERY_TOPIC = `${APP_PREFIX}._peer-discovery._p2p._pubsub`

export const FILE_EXCHANGE_PROTOCOL = `/${APP_PREFIX}-file/1`
export const DIRECT_MESSAGE_PROTOCOL = `/${APP_PREFIX}/dm/1.0.0`
export const DHT_PROTOCOL = `/${APP_PREFIX}/kad/1.0.0`

export const CIRCUIT_RELAY_CODE = 290

// XXX dozy bootstrapper
export const WEBTRANSPORT_BOOTSTRAP_NODE =
  '/ip4/142.93.224.65/udp/1970/quic-v1/webtransport/certhash/uEiBntFDuWbXUuSqg0XrFAfgKLivXbX1uxFtwYUV5vjFTRA/certhash/uEiBOkGfz3B7IcLOFdh4uU3wJQRG6DyUTfjMz8TDxjRBp3Q/p2p/12D3KooWDwgE8vSCx8KtpZHwYEENiutTfLdC7b757ekBTZcGoWqr'

export const WEBRTC_BOOTSTRAP_PEER_ID = "12D3KooWGahRw3ZnM4gAyd9FK75v4Bp5keFYTvkcAwhpEm28wbV3"
export const WEBTRANSPORT_BOOTSTRAP_PEER_ID = "12D3KooWFhXabKDwALpzqMbto94sB7rvmZ6M28hs9Y9xSopDKwQr"

export const P2P_PING_TIMEOUT_MS = 10000
export const P2P_PING_INTERVAL_MS = 15000 // needs to be higher than timeout
export const AutoDialerMaxConnections = 5
