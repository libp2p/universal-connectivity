import { useState } from 'react'
import { useLibp2pContext } from '@/context/ctx'
import { peerIdFromString } from '@libp2p/peer-id'
import Spinner from './spinner'

export default function PeerIDConnect() {
  const { libp2p } = useLibp2pContext()
  const [peerIdInput, setPeerIdInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleConnect = async () => {
    setError(null)

    if (!peerIdInput.trim()) {
      setError('❌ Please enter a valid PeerID')
      return
    }

    if (!libp2p) {
      setError('❌ Libp2p instance not found')
      return
    }

    setLoading(true)
    try {
      // Parse the peer ID string
      const peerId = peerIdFromString(peerIdInput.trim())
      
      // Use libp2p.dial() which handles peer routing internally
      await libp2p.dial(peerId)
      
      setPeerIdInput('')
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : String(e)
      setError(`❌ Error connecting to peer: ${errorMessage}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="my-6 w-full max-w-2xl">
      <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
        <label htmlFor="peer-cid" className="block text-sm font-medium text-gray-900 mb-2">
          Connect to Peer by PeerID
        </label>
        <div className="flex gap-2">
          <input
            value={peerIdInput}
            type="text"
            name="peer-cid"
            id="peer-cid"
            className="flex-1 rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-indigo-600"
            placeholder="Enter PeerID (e.g., 12D3Koo...)"
            onChange={(e) => setPeerIdInput(e.target.value)}
            disabled={loading}
          />
          <button
            type="button"
            className={`inline-flex items-center px-4 py-2 rounded-md
              ${loading ? 'bg-indigo-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-500'}
              text-white font-semibold text-sm transition-colors`}
            onClick={handleConnect}
            disabled={loading}
          >
            {loading ? (
              <>
                <Spinner />
                Connecting...
              </>
            ) : (
              'Connect to PeerID'
            )}
          </button>
        </div>

        {error && <div className="mt-2 text-sm text-red-600">{error}</div>}
      </div>
    </div>
  )
}