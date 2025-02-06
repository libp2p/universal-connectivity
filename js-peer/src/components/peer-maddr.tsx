import { useLibp2pContext } from '@/context/ctx'
import { multiaddr } from '@multiformats/multiaddr'
import { useState } from 'react'
import Spinner from '@/components/spinner'
import { connectToMultiaddr } from '../lib/libp2p'
import type { PeerId } from '@libp2p/interface'

interface PeerMaddrListProps {
  resolvedMultiaddrs: string[]
  setResolvedMultiaddrs: (addrs: string[]) => void
  setError: (error: string | null) => void
}

export default function PeerMaddrList({ resolvedMultiaddrs, setResolvedMultiaddrs, setError }: PeerMaddrListProps) {
  if (resolvedMultiaddrs.length === 0) return null

  return (
    <div className="mt-6 w-full">
      <h4 className="text-lg font-semibold text-gray-900 mb-3">Found {resolvedMultiaddrs.length} addresses:</h4>
      <ul className="p-4 border rounded-lg bg-gray-50 shadow-sm space-y-3">
        {resolvedMultiaddrs.map((addr, index) => (
          <MaddrItem key={index} addr={addr} setResolvedMultiaddrs={setResolvedMultiaddrs} setError={setError} />
        ))}
      </ul>
    </div>
  )
}

interface MaddrItemProps {
  addr: string
  setResolvedMultiaddrs: (addrs: string[]) => void
  setError: (error: string | null) => void
}

function MaddrItem({ addr, setResolvedMultiaddrs, setError }: MaddrItemProps) {
  const [loading, setLoading] = useState(false)
  const { libp2p, connections, setConnections } = useLibp2pContext()

  // Helper to check if address is external
  const isExternalAddress = (addr: string) => {
    return !addr.includes('127.0.0.1') && !addr.includes('localhost') && !addr.includes('::1')
  }

  // Helper to validate transport stack
  const hasValidTransportStack = (addr: string) => {
    const hasWebTransport = addr.includes('webtransport') && addr.includes('certhash')
    const hasWebRTC = addr.includes('webrtc') && addr.includes('certhash')
    const hasQuic = addr.includes('quic-v1')

    return hasWebTransport || (hasWebRTC && hasQuic)
  }

  const handleConnect = async () => {
    setLoading(true)
    try {
      const maddr = multiaddr(addr)
      const peerId = maddr.getPeerId()

      if (!peerId) {
        throw new Error('No peer ID found in multiaddr')
      }

      if (!isExternalAddress(addr)) {
        console.warn('⚠️ Attempting to connect to local address, this might fail:', addr)
      }

      if (!hasValidTransportStack(addr)) {
        throw new Error('Invalid or incomplete transport protocol stack')
      }
      console.log(`🔌 Attempting to connect to ${addr}`)

      // Ensure the multiaddr includes the peer ID
      const fullAddr = addr.includes(`/p2p/${peerId}`) ? addr : `${addr}/p2p/${peerId}`
      const fullMaddr = multiaddr(fullAddr)
      // Attempt connection
      await connectToMultiaddr(libp2p)(fullMaddr)
      console.log('✅ Successfully connected via:', fullAddr)

      if (connections && !connections.find((conn) => conn.remotePeer.toString() === peerId)) {
        const newConnections = [...connections]
        const peerConnections = libp2p.getConnections(peerId as unknown as PeerId)
        if (peerConnections.length > 0) {
          newConnections.push(peerConnections[0])
          setConnections(newConnections)
        }
      }

      setError('✅ Successfully connected to peer!')
      setResolvedMultiaddrs([])
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : String(err)
      console.error('❌ Connection failed:', errorMessage)
      setError(`❌ Failed to connect: ${errorMessage}`)
    } finally {
      setLoading(false)
    }
  }

  // Only show valid multiaddrs that can be used for connection
  const isValidMultiaddr = () => {
    try {
      const maddr = multiaddr(addr)
      return !!maddr.getPeerId() // Only show if it has a peer ID
    } catch {
      return false
    }
  }

  // Only show promising connection candidates
  const getConnectionPriority = () => {
    if (!isValidMultiaddr()) return 0
    let priority = 1
    if (isExternalAddress(addr)) priority += 2
    if (addr.includes('webtransport')) priority += 3
    if (addr.includes('webrtc')) priority += 2
    return priority
  }

  // Don't render if priority is 0 (invalid)
  if (getConnectionPriority() === 0) {
    return null
  }

  return (
    <li className="flex justify-between gap-x-6 py-3">
      <div className="flex min-w-0 gap-x-4">
        <div className="min-w-0 flex-auto">
          <p className="text-sm font-semibold leading-6 text-gray-900 break-all">
            <span
              className={`inline-block px-2 py-1 text-xs rounded-full mr-2 
            ${
              addr.includes('webtransport')
                ? 'bg-green-100 text-green-800'
                : addr.includes('webrtc')
                  ? 'bg-blue-100 text-blue-800'
                  : 'bg-purple-100 text-purple-800'
            }`}
            >
              {addr.includes('webtransport') ? '🌐 WebTransport' : addr.includes('webrtc') ? '🔌 WebRTC' : '🚀 QUIC'}
              {!isExternalAddress(addr) && ' (Local)'}
            </span>
            {addr}
          </p>
        </div>
      </div>

      <div className="hidden sm:flex sm:flex-col sm:items-end">
        <button
          onClick={handleConnect}
          className={`font-bold py-2 px-4 rounded flex flex-row items-center
          ${
            loading
              ? 'bg-gray-400 cursor-not-allowed'
              : getConnectionPriority() > 3
                ? 'bg-green-600 hover:bg-green-700'
                : 'bg-yellow-600 hover:bg-yellow-700'
          } 
          text-white disabled:opacity-70`}
          disabled={loading}
        >
          {loading && <Spinner />}
          <span className="pl-1">
            {loading ? 'Connecting...' : getConnectionPriority() > 3 ? 'Connect (Recommended)' : 'Connect'}
          </span>
        </button>
      </div>
    </li>
  )
}
