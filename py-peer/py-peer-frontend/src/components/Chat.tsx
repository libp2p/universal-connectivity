import { useCallback, useEffect, useRef, useState } from 'react'
import { PaperAirplaneIcon } from '@heroicons/react/24/solid'
import { UsersIcon } from '@heroicons/react/24/outline'
import { usePyPeer } from '../context/PyPeerContext'
import MessageItem from './MessageItem'
import Spinner from './Spinner'

export default function Chat() {
  const {
    nodeInfo,
    topics,
    messages,
    activeTopic,
    setActiveTopic,
    sendMessage,
    markRead,
    connectedPeers,
  } = usePyPeer()

  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [showMobilePeers, setShowMobilePeers] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activeTopic])

  // Mark as read when topic becomes active
  useEffect(() => {
    if (activeTopic) markRead(activeTopic)
  }, [activeTopic, markRead])

  const handleSend = useCallback(
    async (e?: React.FormEvent) => {
      e?.preventDefault()
      const text = input.trim()
      if (!text || !activeTopic) return
      setSending(true)
      try {
        await sendMessage(activeTopic, text)
        setInput('')
      } catch { /* ignore */ }
      finally {
        setSending(false)
      }
    },
    [input, activeTopic, sendMessage],
  )

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const activeMessages = messages[activeTopic] ?? []
  const myPeerId = nodeInfo?.peer_id ?? ''

  const topicList = Object.entries(topics)

  return (
    <div className="flex flex-1 min-h-0 min-w-0">
      {/* ── Topic sidebar ─────────────────────────────────────────────────── */}
      <aside className="hidden sm:flex w-56 flex-col border-r border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between px-3 py-3 border-b border-gray-200">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Topics</span>
        </div>

        <nav className="flex-1 overflow-y-auto py-1">
          {topicList.length === 0 ? (
            <p className="px-3 py-4 text-xs text-gray-400 text-center">No topics yet</p>
          ) : (
            topicList.map(([topic, info]) => (
              <button
                key={topic}
                onClick={() => setActiveTopic(topic)}
                className={`w-full flex items-center justify-between px-3 py-2 text-sm text-left transition ${
                  activeTopic === topic
                    ? 'bg-indigo-50 text-indigo-700 font-medium'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <span className="truncate"># {topic}</span>
                {info.unread_count > 0 && (
                  <span className="ml-1 flex-shrink-0 rounded-full bg-indigo-600 px-1.5 py-0.5 text-xs text-white font-semibold">
                    {info.unread_count}
                  </span>
                )}
              </button>
            ))
          )}
        </nav>

        {/* Peer count */}
        <div className="border-t border-gray-200 px-3 py-2">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            {connectedPeers.length} peer{connectedPeers.length !== 1 ? 's' : ''} connected
          </div>
        </div>
      </aside>

      {/* ── Chat area ─────────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Chat header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold text-gray-900">
              {activeTopic ? `# ${activeTopic}` : 'Select a topic'}
            </span>
          </div>

          <button
            className="sm:hidden flex items-center gap-1 text-sm text-gray-500"
            onClick={() => setShowMobilePeers((v) => !v)}
          >
            <UsersIcon className="h-5 w-5" />
            {connectedPeers.length}
          </button>
        </div>

        {/* Mobile peer list overlay */}
        {showMobilePeers && (
          <div className="sm:hidden border-b border-gray-200 px-4 py-2 bg-gray-50 max-h-40 overflow-y-auto">
            <p className="text-xs font-semibold text-gray-400 mb-1">Connected Peers</p>
            {connectedPeers.length === 0 ? (
              <p className="text-xs text-gray-400">None</p>
            ) : (
              connectedPeers.map((p) => (
                <p key={p} className="text-xs font-mono text-gray-600 truncate">{p}</p>
              ))
            )}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {activeMessages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-gray-400 text-sm">
              <span className="text-3xl">💬</span>
              <span>No messages yet in # {activeTopic}</span>
            </div>
          ) : (
            activeMessages.map((msg, i) => (
              <MessageItem
                key={`${msg.sender_id}-${msg.timestamp}-${i}`}
                message={msg}
                isOwn={msg.sender_id === myPeerId}
              />
            ))
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form
          onSubmit={handleSend}
          className="border-t border-gray-200 px-4 py-3 flex items-end gap-2"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            rows={1}
            placeholder={activeTopic ? `Message #${activeTopic}…` : 'Select a topic first'}
            disabled={!activeTopic || sending}
            className="flex-1 resize-none rounded-xl border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-gray-50 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={!activeTopic || !input.trim() || sending}
            className="flex-shrink-0 flex items-center justify-center rounded-xl bg-indigo-600 p-2.5 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {sending ? (
              <Spinner className="h-4 w-4 text-white" />
            ) : (
              <PaperAirplaneIcon className="h-4 w-4" />
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
