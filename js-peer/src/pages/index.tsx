import Head from 'next/head'
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/20/solid'
import Nav from '@/components/nav'
import { useLibp2pContext } from '@/context/ctx'
import type { Connection } from '@libp2p/interface/connection'
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
  const [dialling, setDialling] = useState(false)
  const [err, setErr] = useState('')

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
      setErr('')

      if (!maddr) {
        return
      }

      setDialling(true)

      try {
        const connection = await connectToMultiaddr(libp2p)(multiaddr(maddr))
        console.log('connection: ', connection)

        return connection
      } catch (e: any) {
        if (e && e.message) {
          setErr(e.message)
        }
        console.error(e)
      } finally {
        setDialling(false)
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
                  className={"rounded-md bg-indigo-600 my-2 py-2 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600" + (dialling ? ' cursor-not-allowed' : '')}
                  onClick={handleConnectToMultiaddr}
                  disabled={dialling}
                >
                  {dialling && (
                    <svg className="inline-block text-gray-300 animate-spin" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"
                    width="20" height="20">
                    <path
                      d="M32 3C35.8083 3 39.5794 3.75011 43.0978 5.20749C46.6163 6.66488 49.8132 8.80101 52.5061 11.4939C55.199 14.1868 57.3351 17.3837 58.7925 20.9022C60.2499 24.4206 61 28.1917 61 32C61 35.8083 60.2499 39.5794 58.7925 43.0978C57.3351 46.6163 55.199 49.8132 52.5061 52.5061C49.8132 55.199 46.6163 57.3351 43.0978 58.7925C39.5794 60.2499 35.8083 61 32 61C28.1917 61 24.4206 60.2499 20.9022 58.7925C17.3837 57.3351 14.1868 55.199 11.4939 52.5061C8.801 49.8132 6.66487 46.6163 5.20749 43.0978C3.7501 39.5794 3 35.8083 3 32C3 28.1917 3.75011 24.4206 5.2075 20.9022C6.66489 17.3837 8.80101 14.1868 11.4939 11.4939C14.1868 8.80099 17.3838 6.66487 20.9022 5.20749C24.4206 3.7501 28.1917 3 32 3L32 3Z"
                      stroke="white" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"></path>
                    <path
                      d="M32 3C36.5778 3 41.0906 4.08374 45.1692 6.16256C49.2477 8.24138 52.7762 11.2562 55.466 14.9605C58.1558 18.6647 59.9304 22.9531 60.6448 27.4748C61.3591 31.9965 60.9928 36.6232 59.5759 40.9762"
                      stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" className="text-indigo-500">
                    </path>
                  </svg>)}{' '}
                  Connect to multiaddr
                </button>
                {err && <p className="text-red-500">{err}</p>}
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
