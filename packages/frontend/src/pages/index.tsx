import Head from 'next/head'
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/20/solid'
import Nav from '@/components/nav'
import { useLibp2pContext } from '@/context/ctx'
import type { Connection } from '@libp2p/interface-connection'
import { usePeerContext } from '../context/peer-ctx'
import { useCallback, useEffect, useState } from 'react'
import Image from 'next/image'
import { multiaddr } from '@multiformats/multiaddr'
import { connectToMultiaddr } from '../lib/libp2p'
import { useListenAddressesContext } from '../context/listen-addresses-ctx'

export default function Home() {
  const { libp2p } = useLibp2pContext()
  const { peerStats, setPeerStats } = usePeerContext()
  const { listenAddresses, setListenAddresses } = useListenAddressesContext()
  const [maddr, setMultiaddr] = useState('')

  useEffect(() => {
    const interval = setInterval(() => {
      const connections = libp2p.getConnections()

      setPeerStats({
        ...peerStats,
        peerIds: connections.map(conn => conn.remotePeer),
        connections: connections,
        connected: connections.length > 0,
      })
    }, 1000)

    return () => {
      clearInterval(interval)
    }
  }, [libp2p, peerStats, setPeerStats])

  useEffect(() => {
    const interval = setInterval(() => {
      const multiaddrs = libp2p.getMultiaddrs()

      setListenAddresses({
        ...listenAddresses,
        multiaddrs
      })
    }, 1000)

    return () => {
      clearInterval(interval)
    }
  }, [libp2p, listenAddresses, setListenAddresses])

  type PeerProtoTuple = {
    peerId: string
    protocols: string[]
  }

  const getFormattedConnections = (connections: Connection[]): PeerProtoTuple[] => {
    const protoNames: Map<string, string[]> = new Map()

    connections.forEach((conn) => {
      const exists = protoNames.get(conn.remotePeer.toString())
      const dedupedProtonames = [...new Set(conn.remoteAddr.protoNames())]

      if (exists?.length) {
        const namesToAdd = dedupedProtonames.filter((name) => !exists.includes(name))
        // console.log('namesToAdd: ', namesToAdd)
        protoNames.set(conn.remotePeer.toString(), [...exists, ...namesToAdd])

      } else {
        protoNames.set(conn.remotePeer.toString(), dedupedProtonames)
      }
    })

    return [...protoNames.entries()].map(([peerId, protocols]) => ({
      peerId,
      protocols,
    }))
  }

  const handleConnectToMultiaddr = useCallback(
    async (e: React.MouseEvent<HTMLButtonElement>) => {
      if (!maddr) {
        return
      }

      try {
        const connection = await connectToMultiaddr(libp2p)(multiaddr(maddr))
        console.log('connection: ', connection)

        return connection
      } catch (e) {
        console.error(e)
      }
    },
    [libp2p, maddr],
  )

  // handleConnectToMultiaddr

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
                <Image
                  src="/libp2p-hero.svg"
                  alt="libp2p logo"
                  height="46"
                  width="46"
                />
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
                {
                  listenAddresses.multiaddrs.map((ma, index) => {
                    return (
                      <li key={`ma-${index}`}>{ma.toString()}</li>
                    )
                  })
                }
              </ul>
              <div className="my-6 w-1/2">
                <label
                  htmlFor="peer-id"
                  className="block text-sm font-medium leading-6 text-gray-900"
                >
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
                  className="rounded-md bg-indigo-600 my-2 py-2 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                  onClick={handleConnectToMultiaddr}
                >
                  Connect to multiaddr
                </button>
              </div>

              <div className="my-4 inline-flex items-center text-xl">
                Connected:{' '}
                {peerStats.connected ? (
                  <CheckCircleIcon className="inline w-6 h-6 text-green-500" />
                ) : (
                  <XCircleIcon className="w-6 h-6 text-red-500" />
                )}
              </div>
              <div>
                {peerStats.peerIds.length > 0 ? (
                  <>
                    <h3 className="text-xl">
                      {' '}
                      Connected peers ({getFormattedConnections(peerStats.connections).length}) 👇
                    </h3>
                    <pre className="px-2">
                      {getFormattedConnections(peerStats.connections)
                        .map(
                          (pair) =>
                            `${pair.peerId} (${pair.protocols.join(', ')})`,
                        )
                        .join('\n')}
                    </pre>
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
