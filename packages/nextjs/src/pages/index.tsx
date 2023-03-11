import Head from 'next/head'
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/20/solid'
import Nav from '@/components/nav'
import { useLibp2pContext } from '@/context/ctx'
import { useEffect, useState } from 'react'
import { connectToPeer, getPeerMultiaddrs } from '@/lib/libp2p'
import type { Multiaddr } from '@multiformats/multiaddr'

const APP_PEER = '12D3KooWBdmLJjhpgJ9KZgLM3f894ff9xyBfPvPjFNn7MKJpyrC2'
// const APP_PEER = '12D3KooWRBy97UB99e3J6hiPesre1MZeuNQvfan4gBziswrRJsNK'

export default function Home() {
  const { libp2p } = useLibp2pContext()
  const [isConnected, setIsConnected] = useState(false)
  const [multiaddrs, setMultiaddrs] = useState<Multiaddr[]>()

  // Effect hook to connect to a specific peer when the page loads
  useEffect(() => {
    const connect = async () => {
      const addrs = await getPeerMultiaddrs(libp2p)(APP_PEER)
      setMultiaddrs(addrs)

      await connectToPeer(libp2p)(addrs)
    }

    connect()
      .then(() => {
        setIsConnected(true)
      })
      .catch((e) => {
        console.error(e)
        setIsConnected(false)
      })
  }, [setIsConnected, setMultiaddrs, libp2p])

  return (
    <>
      <Head>
        <title>js-libp2p-nextjs-example</title>
        <meta name="description" content="js-libp2p-nextjs-example" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>
      <main className="min-h-full">
        <Nav />
        <div className="py-10">
          <header>
            <div className="mx-auto max-w-7xl px-2 sm:px-6 lg:px-8">
              <h1 className="text-3xl font-bold leading-tight tracking-tight text-gray-900">
                Libp2p WebTransport Example
              </h1>
            </div>
          </header>
          <main>
            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
              <ul className="my-2 space-y-2 break-all">
                <li className="">
                  This PeerID: {libp2p.peerId.toString()}
                </li>
                <li>Multiaddrs for {APP_PEER} 👇</li>
              </ul>
              {multiaddrs && (
                <pre className="px-2">
                  {multiaddrs.map((peer) => peer.toString()).join('\n')}
                </pre>
              )}
              <p className="inline-flex items-center">
                Connected:{' '}
                {isConnected ? (
                  <CheckCircleIcon className="inline w-6 h-6 text-green-500" />
                ) : (
                  <XCircleIcon className="w-6 h-6 text-red-500" />
                )}
              </p>
            </div>
          </main>
        </div>
      </main>
    </>
  )
}
