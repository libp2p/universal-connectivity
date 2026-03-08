import { useEffect, useRef, useState } from 'react'
import { SparklesIcon, XMarkIcon, PaperAirplaneIcon, ChevronDownIcon } from '@heroicons/react/24/solid'
import Spinner from './Spinner'
import { BASE } from '../api/client'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}

async function askQuestion(question: string): Promise<{ answer: string; sources: string[] }> {
  const res = await fetch(`${BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  const data = await res.json()
  if (!data.success) throw new Error(data.error ?? 'Unknown error')
  return { answer: data.answer, sources: data.sources ?? [] }
}

export default function LibP2PAssistant() {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleAsk() {
    const question = input.trim()
    if (!question || loading) return
    setInput('')
    setError('')
    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setLoading(true)
    try {
      const { answer, sources } = await askQuestion(question)
      setMessages((prev) => [...prev, { role: 'assistant', content: answer, sources }])
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Could not reach the assistant.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleAsk()
    }
  }

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-2">
      {/* ── Chat panel ──────────────────────────────────────────────── */}
      {open && (
        <div className="w-80 sm:w-96 flex flex-col rounded-xl border border-gray-200 bg-white shadow-2xl overflow-hidden"
             style={{ maxHeight: '520px' }}>
          {/* Header */}
          <div className="flex items-center justify-between bg-indigo-600 px-4 py-3">
            <div className="flex items-center gap-2">
              <SparklesIcon className="h-4 w-4 text-white" />
              <span className="text-sm font-semibold text-white">py-libp2p Assistant</span>
            </div>
            <button onClick={() => setOpen(false)} className="text-white/80 hover:text-white">
              <XMarkIcon className="h-4 w-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 bg-gray-50"
               style={{ minHeight: '280px', maxHeight: '360px' }}>
            {messages.length === 0 && !loading && (
              <p className="text-xs text-gray-400 text-center pt-6">
                Ask anything about py-libp2p APIs, DHT, PubSub protocols, or debugging connection issues.
              </p>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`flex flex-col gap-1 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                <div className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-br-sm'
                    : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm'
                }`}>
                  {msg.content}
                </div>
                {msg.sources && msg.sources.length > 0 && (
                  <details className="max-w-[85%] text-[10px] text-gray-400">
                    <summary className="cursor-pointer hover:text-gray-600 flex items-center gap-1">
                      <ChevronDownIcon className="h-2.5 w-2.5" />
                      {msg.sources.length} source{msg.sources.length > 1 ? 's' : ''}
                    </summary>
                    <ul className="mt-1 space-y-0.5 pl-2">
                      {msg.sources.map((s, j) => (
                        <li key={j} className="truncate font-mono">{s.replace(/.*\/(py-libp2p|specs)\//, '$1/')}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex items-start gap-2">
                <div className="bg-white border border-gray-200 rounded-xl rounded-bl-sm px-3 py-2 text-xs text-gray-500 flex items-center gap-1.5 shadow-sm">
                  <Spinner className="h-3 w-3 text-indigo-500" /> Thinking…
                </div>
              </div>
            )}
            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-600">
                {error}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 bg-white px-3 py-2 flex items-end gap-2">
            <textarea
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask about py-libp2p…"
              disabled={loading}
              className="flex-1 resize-none rounded-lg border border-gray-300 px-2.5 py-1.5 text-xs placeholder-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-gray-50"
            />
            <button
              onClick={handleAsk}
              disabled={loading || !input.trim()}
              className="flex-shrink-0 flex items-center justify-center rounded-lg bg-indigo-600 p-1.5 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              {loading
                ? <Spinner className="h-3.5 w-3.5 text-white" />
                : <PaperAirplaneIcon className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
      )}

      {/* ── Toggle button ────────────────────────────────────────────── */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg hover:bg-indigo-700 transition"
      >
        <SparklesIcon className="h-4 w-4" />
        {open ? 'Close' : 'Ask py-libp2p'}
      </button>
    </div>
  )
}
