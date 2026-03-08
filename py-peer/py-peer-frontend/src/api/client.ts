// ─── Types ────────────────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  success: boolean
  data: T
  error: { code: number; message: string; detail: string | null } | null
  timestamp: number
}

export interface NodeInfo {
  peer_id: string
  nickname: string
  multiaddr: string
  port: number
  ready: boolean
  uptime_seconds: number
}

export interface ServiceStatus {
  ready: boolean
  running: boolean
  uptime_seconds: number
  peer_count: number
}

export interface ServiceConfig {
  nickname: string
  port: number
  topic: string | null
  strict_signing: boolean
  download_dir: string
  connect_addrs: string[]
}

export interface TopicInfo {
  unread_count: number
  total_count: number
  last_message: ChatMessage | null
}

export interface ChatMessage {
  type: 'chat_message' | 'file_message' | 'file_shared' | 'file_downloaded'
  message?: string
  sender_nick: string
  sender_id: string
  timestamp: number
  topic: string
  read: boolean
  file_cid?: string
  file_name?: string
  file_size?: number
}

export interface PubSubConfig {
  degree: number
  degree_low: number
  degree_high: number
  heartbeat_interval: number
  protocols: string[]
}

export interface DHTStatus {
  mode: string
  random_walk_enabled: boolean
  routing_table_size: number
}

// ─── Base URL ─────────────────────────────────────────────────────────────────
// In development the Vite proxy forwards /api/* → localhost:8765, so VITE_API_URL
// can be left empty.  In production (Vercel / Netlify) set it to your backend's
// full origin, e.g.  VITE_API_URL=https://your-backend.example.com

const API_ORIGIN: string = import.meta.env.VITE_API_URL ?? ''
export const BASE = `${API_ORIGIN}/api/v1`

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  const json: ApiResponse<T> = await res.json()
  if (!json.success) throw new Error(json.error?.message ?? 'API error')
  return json.data
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const json: ApiResponse<T> = await res.json()
  if (!json.success) throw new Error(json.error?.message ?? 'API error')
  return json.data
}

async function put<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'PUT' })
  const json: ApiResponse<T> = await res.json()
  if (!json.success) throw new Error(json.error?.message ?? 'API error')
  return json.data
}

// ─── Node ─────────────────────────────────────────────────────────────────────

export const getNodeInfo = () => get<NodeInfo>('/node/info')
export const getServiceStatus = () => get<ServiceStatus>('/service/status')
export const getServiceConfig = () => get<ServiceConfig>('/service/config')

// ─── Peers ────────────────────────────────────────────────────────────────────

export const getPeers = () => get<{ peers: string[]; count: number }>('/peers')
export const getKnownPeers = () => get<{ peers: string[]; count: number }>('/peers/known')
export const connectToPeer = (multiaddr: string) =>
  post<{ message: string; multiaddr: string }>('/peers/connect', { multiaddr })

// ─── Topics ───────────────────────────────────────────────────────────────────

export const getTopics = () =>
  get<{ topics: Record<string, TopicInfo>; count: number }>('/topics')
export const subscribeTopic = (topic: string) =>
  post<{ message: string; topic: string }>('/topics', { topic })

// ─── Messages ─────────────────────────────────────────────────────────────────

export const getMessages = (topic: string, limit = 100, offset = 0) =>
  get<{ messages: ChatMessage[]; total: number; limit: number; offset: number }>(
    `/messages/${encodeURIComponent(topic)}?limit=${limit}&offset=${offset}`,
  )
export const sendMessage = (topic: string, message: string) =>
  post<{ message: string; topic: string }>(`/messages/${encodeURIComponent(topic)}`, { message })
export const getUnread = (topic: string) =>
  get<{ unread_count: number }>(`/messages/${encodeURIComponent(topic)}/unread`)
export const markRead = (topic: string) =>
  put<{ message: string }>(`/messages/${encodeURIComponent(topic)}/read`)

// ─── PubSub / DHT ─────────────────────────────────────────────────────────────

export const getPubSubConfig = () => get<PubSubConfig>('/pubsub/config')
export const getDHTStatus = () => get<DHTStatus>('/dht/status')
export const getPubSubMesh = () =>
  get<{ mesh: Record<string, string[]>; total_mesh_peers: number }>('/pubsub/mesh')

// ─── WebSocket helpers ────────────────────────────────────────────────────────

export const WS_BASE: string = API_ORIGIN
  ? API_ORIGIN.replace(/^http/, 'ws')
  : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`

export const wsMessages = () => new WebSocket(`${WS_BASE}/ws/messages`)
export const wsPeers = () => new WebSocket(`${WS_BASE}/ws/peers`)
export const wsSystem = () => new WebSocket(`${WS_BASE}/ws/system`)
