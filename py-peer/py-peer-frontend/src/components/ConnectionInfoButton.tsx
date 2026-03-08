import { useState } from 'react'
import { ClipboardIcon, ClipboardDocumentCheckIcon } from '@heroicons/react/24/outline'
import { usePyPeer } from '../context/PyPeerContext'

export default function ConnectionInfoButton() {
  const { nodeInfo } = usePyPeer()
  const [copied, setCopied] = useState(false)

  if (!nodeInfo) return null

  const copyMultiaddr = () => {
    navigator.clipboard.writeText(nodeInfo.multiaddr).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <button
      onClick={copyMultiaddr}
      title="Copy multiaddr to clipboard"
      className="flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 transition"
    >
      {copied ? (
        <ClipboardDocumentCheckIcon className="h-4 w-4 text-green-500" />
      ) : (
        <ClipboardIcon className="h-4 w-4" />
      )}
      <span className="hidden sm:inline truncate max-w-[180px]">{nodeInfo.peer_id.slice(0, 12)}…</span>
    </button>
  )
}
