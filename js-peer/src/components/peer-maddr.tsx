import { useLibp2pContext } from '@/context/ctx'
import { multiaddr } from '@multiformats/multiaddr'
import { useState } from 'react'
import Spinner from '@/components/spinner'
import { connectToMultiaddr } from '../lib/libp2p'

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
  const { libp2p } = useLibp2pContext()

  const handleConnect = async () => {
    try {
      setLoading(true)
      const maddr = multiaddr(addr.toString())
      await connectToMultiaddr(libp2p)(maddr)
      setResolvedMultiaddrs([])
    } catch (e: any) {
      setError(e?.message ?? 'Error connecting')
    } finally {
      setLoading(false)
    }
  }

  return (
    // <li className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 bg-white rounded-lg border border-gray-100 hover:border-gray-200 transition-all">
    //   <span className="w-full sm:w-3/4 text-sm md:text-base font-medium text-gray-700 break-all">
    //     {addr}
    //   </span>
    //   <button
    //     onClick={handleConnect}
    //     className="w-full sm:w-auto whitespace-nowrap px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-md font-medium transition-colors duration-200 flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed"
    //     disabled={loading}
    //   >
    //     {loading && <Spinner />}
    //     <span>{loading ? 'Connecting...' : 'Connect to Peer'}</span>
    //   </button>
    // </li>
    <li className="flex justify-between gap-x-6 py-3">
      <div className="flex min-w-0 gap-x-4">
        <div className="mt-1 flex items-center gap-x-1.5">
          <div className="flex-none rounded-full bg-emerald-500/20 p-1">
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          </div>
        </div>
        <div className="min-w-0 flex-auto">
          <p className="text-sm font-semibold leading-6 text-gray-900 break-all">{addr}</p>
        </div>
      </div>

      <div className="hidden sm:flex sm:flex-col sm:items-end">
        <button
          onClick={handleConnect}
          className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded flex flex-row items-center disabled:opacity-70 disabled:cursor-not-allowed"
          disabled={loading}
        >
          {loading && <Spinner />}
          <span className="pl-1">{loading ? 'Connecting...' : 'Connect'}</span>
        </button>
      </div>
    </li>
  )
}
