import Head from 'next/head'
import Nav from '@/components/nav'
import { useLibp2pContext } from '@/context/ctx'
import type { PeerUpdate } from '@libp2p/interface'
import { useCallback, useEffect, useState } from 'react'
import Image from 'next/image'
import { Multiaddr, multiaddr } from '@multiformats/multiaddr'
import { connectToMultiaddr } from '../lib/libp2p'
import Spinner from '@/components/spinner'
import PeerList from '@/components/peer-list'
import PeerIDConnect from '@/components/peerID-connect'

export default function Home() {
  const { libp2p, connections } = useLibp2pContext()
  const [listenAddresses, setListenAddresses] = useState<Multiaddr[]>([])
  const [maddr, setMultiaddr] = useState('')
  const [dialling, setDialling] = useState(false)
  const [err, setErr] = useState('')


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
              <PeerIDConnect />
              <div>
                {connections.length > 0 ? (
                  <>
                    <h3 className="text-xl">Connections ({connections.length}):</h3>
                    <PeerList connections={connections} />
                  </>
                ) : null}
              </div>
            </div>
          </main>
        </div>
      </main>
    </>
  )
}
