import Head from 'next/head'
import Nav from '@/components/nav'
import { useLibp2pContext } from '@/context/ctx'
import type { PeerUpdate, Connection } from '@libp2p/interface'
import { useCallback, useEffect, useState } from 'react'
import Image from 'next/image'
import { Multiaddr, multiaddr } from '@multiformats/multiaddr'
import { connectToMultiaddr, findPeerById } from '../lib/libp2p'
import Spinner from '@/components/spinner'
import PeerList from '@/components/peer-list'
import PeerMaddrList from "@/components/peer-maddr";

export default function Home() {
  const { libp2p } = useLibp2pContext()
  const [connections, setConnections] = useState<Connection[]>([])
  const [listenAddresses, setListenAddresses] = useState<Multiaddr[]>([])
  const [maddr, setMultiaddr] = useState('')
  const [dialling, setDialling] = useState(false)
  const [err, setErr] = useState('')
  /*peerID */
  const [peerIdInput, setPeerIdInput] = useState("");
  const [resolvedMultiaddrs, setResolvedMultiaddrs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>("");
  const [loading, setLoading] = useState(false);

  const handleFindPeer = async () => {
    setError("");
    setResolvedMultiaddrs([]);
    
    // Input validation
    if (!peerIdInput.trim()) {
      setError("❌ Please enter a valid PeerID");
      return;
    }
  
    if (!libp2p) {
      setError("❌ Libp2p instance not found");
      return;
    }
  
    setLoading(true);
    try {
      const peerInfo = await findPeerById(libp2p)(peerIdInput.trim());
      
      if (!peerInfo?.addresses?.length) {
        setError("⚠️ Peer not found or no multiaddrs available");
        return;
      }
  
      // Extract multiaddrs from peer info
      const multiaddrs = peerInfo.addresses.map(addr => addr.multiaddr.toString());
      console.log("✅ Found peer with addresses:", multiaddrs);
      setResolvedMultiaddrs(multiaddrs);
      setPeerIdInput(""); 
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : String(e);
      setError(`❌ Error finding peer: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const onConnection = () => {
      const connections = libp2p.getConnections()
      setConnections(connections)
    }
    onConnection()
    libp2p.addEventListener('connection:open', onConnection)
    libp2p.addEventListener('connection:close', onConnection)
    return () => {
      libp2p.removeEventListener('connection:open', onConnection)
      libp2p.removeEventListener('connection:clone', onConnection)
    }
  }, [libp2p, setConnections])

  useEffect(() => {
    const onPeerUpdate = (evt: CustomEvent<PeerUpdate>) => {
      const maddrs = evt.detail.peer.addresses?.map((p) => p.multiaddr)
      setListenAddresses(maddrs ?? [])
    }
    libp2p.addEventListener('self:peer:update', onPeerUpdate)

    return () => {
      libp2p.removeEventListener('self:peer:update', onPeerUpdate)
    }
  }, [libp2p, setListenAddresses])

  const handleConnectToMultiaddr = useCallback(
    async (e: React.MouseEvent<HTMLButtonElement>) => {
      setErr('')
      if (!maddr) {
        return
      }
      setDialling(true)
      try {
        await connectToMultiaddr(libp2p)(multiaddr(maddr))
      } catch (e: any) {
        setErr(e?.message ?? 'Error connecting')
      } finally {
        setDialling(false)
      }
    },
    [libp2p, maddr],
  )

  const handleMultiaddrChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setMultiaddr(e.target.value)
    },
    [setMultiaddr],
  )

  return (
    <>
      <Head>
        <title>Universal Connectivity</title>
        <meta name="description" content="universal connectivity" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>
      <main className="min-h-full">
        <Nav />
        <div className="py-10">
          <header>
            <div className="mx-auto max-w-7xl px-2 sm:px-6 lg:px-8">
              <h1 className="text-3xl font-bold leading-tight tracking-tight text-gray-900 flex flex-row">
                <p className="mr-4">Universal Connectivity</p>
                <Image src="/libp2p-hero.svg" alt="libp2p logo" height="46" width="46" />
              </h1>
            </div>
          </header>
          <main>
            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
              <ul className="my-2 space-y-2 break-all">
                <li className="">This PeerID: {libp2p.peerId.toString()}</li>
              </ul>
              Addresses:
              <ul className="my-2 space-y-2 break-all">
                {listenAddresses.map((ma, index) => (
                  <li className="text-xs text-gray-700" key={`ma-${index}`}>
                    {ma.toString()}
                  </li>
                ))}
              </ul>
              <div className="my-6 w-1/2">
                <label htmlFor="peer-id" className="block text-sm font-medium leading-6 text-gray-900">
                  multiaddr to connect to
                </label>
                <div className="mt-2">
                  <input
                    value={maddr}
                    type="text"
                    name="peer-id"
                    id="peer-id"
                    className="block w-full rounded-md border-0 py-1.5 px-3 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                    placeholder="12D3Koo..."
                    aria-describedby="multiaddr-id-description"
                    onChange={handleMultiaddrChange}
                  />
                </div>
                <button
                  type="button"
                  className={
                    'rounded-md bg-indigo-600 my-2 py-2 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600' +
                    (dialling ? ' cursor-not-allowed' : '')
                  }
                  onClick={handleConnectToMultiaddr}
                  disabled={dialling}
                >
                  {dialling && <Spinner />} Connect{dialling && 'ing'} to multiaddr
                </button>
                {err && <p className="text-red-500">{err}</p>}
              </div>
              <div>
                {connections.length > 0 ? (
                  <>
                    <h3 className="text-xl">Connections ({connections.length}):</h3>
                    <PeerList connections={connections} />
                  </>
                ) : null}
              </div>
              {/* CONNECT BY PEER-ID */}
              <div className="my-6 w-full max-w-2xl">
                <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
                  <label
                    htmlFor="peer-cid"
                    className="block text-sm font-medium text-gray-900 mb-2"
                  >
                    Find Peer by PeerID
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
                        ${
                          loading
                          ? "bg-indigo-400 cursor-not-allowed"
                          : "bg-indigo-600 hover:bg-indigo-500"
                        }
          text-white font-semibold text-sm transition-colors`}
                      onClick={handleFindPeer}
                      disabled={loading}
                    >
                      {loading ? (
                        <>
                          <Spinner />
                          Searching...
                        </>
                      ) : ("Find Peer")}
                    </button>
                  </div>

                  {/* Error Message */}
                  {error && (
                    <div className="mt-2 text-sm text-red-600">{error}</div>
                  )}
                  {resolvedMultiaddrs.length > 0 && (
                    <div className="mt-4">
                      <h4 className="text-sm font-medium text-gray-900 mb-2">
                        Found {resolvedMultiaddrs.length} multiaddrs:
                      </h4>
                      <PeerMaddrList
                        resolvedMultiaddrs={resolvedMultiaddrs}
                        setResolvedMultiaddrs={setResolvedMultiaddrs}
                        setError={setError}
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
          </main>
        </div>
      </main>
    </>
  )
}
