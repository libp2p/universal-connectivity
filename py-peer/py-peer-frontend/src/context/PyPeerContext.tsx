import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react'
import * as api from '../api/client'
import type { ChatMessage, NodeInfo, ServiceStatus, TopicInfo } from '../api/client'

// ─── Types ────────────────────────────────────────────────────────────────────

interface PeerPeerState {
  nodeInfo: NodeInfo | null
  status: ServiceStatus | null
  // keyed by topic name
  topics: Record<string, TopicInfo>
  // keyed by topic name
  messages: Record<string, ChatMessage[]>
  connectedPeers: string[]
  loading: boolean
  error: string
  activeTopic: string
  setActiveTopic: (topic: string) => void
  sendMessage: (topic: string, text: string) => Promise<void>
  connectPeer: (maddr: string) => Promise<void>
  subscribeTopic: (topic: string) => Promise<void>
  refreshPeers: () => void
  markRead: (topic: string) => void
}

// ─── Context ──────────────────────────────────────────────────────────────────

const PyPeerContext = createContext<PeerPeerState | null>(null)

export function usePyPeer(): PeerPeerState {
  const ctx = useContext(PyPeerContext)
  if (!ctx) throw new Error('usePyPeer must be used inside <PyPeerProvider>')
  return ctx
}

// ─── Provider ─────────────────────────────────────────────────────────────────

const DEFAULT_TOPIC = 'universal-connectivity'
const POLL_INTERVAL = 5000

export function PyPeerProvider({ children }: { children: React.ReactNode }) {
  const [nodeInfo, setNodeInfo] = useState<NodeInfo | null>(null)
  const [status, setStatus] = useState<ServiceStatus | null>(null)
  const [topics, setTopics] = useState<Record<string, TopicInfo>>({})
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({})
  const [connectedPeers, setConnectedPeers] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTopic, setActiveTopic] = useState(DEFAULT_TOPIC)

  // ── Initial load ─────────────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false

    async function init() {
      try {
        const [info, svc] = await Promise.all([api.getNodeInfo(), api.getServiceStatus()])
        if (cancelled) return
        setNodeInfo(info)
        setStatus(svc)
        setLoading(false)
      } catch (e: unknown) {
        if (cancelled) return
        setError(`Cannot reach py-peer API at localhost:8765. Start with: python main.py --api`)
        setLoading(false)
      }
    }

    init()
    return () => { cancelled = true }
  }, [])

  // ── Poll topics + peers ───────────────────────────────────────────────────

  const refreshTopics = useCallback(async () => {
    try {
      const { topics } = await api.getTopics()
      setTopics(topics)
    } catch { /* silent */ }
  }, [])

  const refreshPeers = useCallback(async () => {
    try {
      const { peers } = await api.getPeers()
      setConnectedPeers(peers)
      const svc = await api.getServiceStatus()
      setStatus(svc)
    } catch { /* silent */ }
  }, [])

  useEffect(() => {
    if (loading) return
    refreshTopics()
    refreshPeers()
    const id = setInterval(() => {
      refreshTopics()
      refreshPeers()
    }, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [loading, refreshTopics, refreshPeers])

  // ── WebSocket: real-time message feed ────────────────────────────────────

  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (loading) return

    function connect() {
      const ws = api.wsMessages()
      wsRef.current = ws

      ws.onmessage = (evt) => {
        try {
          const frame = JSON.parse(evt.data as string) as { event: string; data: ChatMessage }
          const msg = frame.data
          if (!msg?.topic) return

          setMessages((prev) => {
            const existing = prev[msg.topic] ?? []
            // deduplicate by sender+timestamp+message
            const dup = existing.some(
              (m) => m.timestamp === msg.timestamp && m.sender_id === msg.sender_id && m.message === msg.message,
            )
            if (dup) return prev
            return { ...prev, [msg.topic]: [...existing, msg] }
          })

          // refresh unread count in topics
          setTopics((prev) => {
            const t = prev[msg.topic]
            if (!t) return prev
            return {
              ...prev,
              [msg.topic]: { ...t, unread_count: t.unread_count + 1, total_count: t.total_count + 1, last_message: msg },
            }
          })
        } catch { /* ignore malformed */ }
      }

      ws.onclose = () => {
        // Reconnect after 3 s
        setTimeout(connect, 3000)
      }
    }

    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [loading])

  // ── WebSocket: peer updates ───────────────────────────────────────────────

  const wsPeersRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (loading) return

    function connect() {
      const ws = api.wsPeers()
      wsPeersRef.current = ws

      ws.onmessage = (evt) => {
        try {
          const frame = JSON.parse(evt.data as string) as {
            event: string
            data: { connected_peers: string[]; peer_count: number }
          }
          if (frame.event === 'peer_update') {
            setConnectedPeers(frame.data.connected_peers)
          }
        } catch { /* ignore */ }
      }

      ws.onclose = () => setTimeout(connect, 3000)
    }

    connect()
    return () => { wsPeersRef.current?.close() }
  }, [loading])

  // ── Fetch historical messages for active topic ─────────────────────────

  useEffect(() => {
    if (!activeTopic || loading) return
    api.getMessages(activeTopic).then(({ messages: msgs }) => {
      setMessages((prev) => ({ ...prev, [activeTopic]: msgs }))
    }).catch(() => { /* topic may not exist yet */ })
  }, [activeTopic, loading])

  // ── Actions ───────────────────────────────────────────────────────────────

  const sendMessage = useCallback(async (topic: string, text: string) => {
    await api.sendMessage(topic, text)
    // Optimistically add own message
    const optimistic: ChatMessage = {
      type: 'chat_message',
      message: text,
      sender_nick: nodeInfo?.nickname ?? 'you',
      sender_id: nodeInfo?.peer_id ?? 'self',
      timestamp: Date.now() / 1000,
      topic,
      read: true,
    }
    setMessages((prev) => ({ ...prev, [topic]: [...(prev[topic] ?? []), optimistic] }))
  }, [nodeInfo])

  const connectPeer = useCallback(async (maddr: string) => {
    await api.connectToPeer(maddr)
    setTimeout(refreshPeers, 1500)
  }, [refreshPeers])

  const subscribeTopic = useCallback(async (topic: string) => {
    await api.subscribeTopic(topic)
    setTimeout(refreshTopics, 1000)
  }, [refreshTopics])

  const markRead = useCallback((topic: string) => {
    api.markRead(topic).catch(() => {})
    setTopics((prev) => {
      const t = prev[topic]
      if (!t) return prev
      return { ...prev, [topic]: { ...t, unread_count: 0 } }
    })
    setMessages((prev) => {
      const msgs = (prev[topic] ?? []).map((m) => ({ ...m, read: true }))
      return { ...prev, [topic]: msgs }
    })
  }, [])

  return (
    <PyPeerContext.Provider
      value={{
        nodeInfo,
        status,
        topics,
        messages,
        connectedPeers,
        loading,
        error,
        activeTopic,
        setActiveTopic,
        sendMessage,
        connectPeer,
        subscribeTopic,
        markRead,
        refreshPeers,
      }}
    >
      {children}
    </PyPeerContext.Provider>
  )
}
