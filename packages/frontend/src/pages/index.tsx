import Head from 'next/head'
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/20/solid'
import Nav from '@/components/nav'
import { useLibp2pContext } from '@/context/ctx'
import { useInterval } from 'usehooks-ts'

import type { Connection } from '@libp2p/interface-connection'
import { usePeerContext } from '../context/peer-ctx'


export default function Home() {
  const { libp2p } = useLibp2pContext()
  const { peerStats, setPeerStats } = usePeerContext()

  useInterval(() => {
    const getConnectedPeers = async () => {
      return await libp2p.getPeers()
    }
    const getConnections = async () => {
      return await libp2p.getConnections()
    }

    const ping = async () => {
      const { peerIds } = peerStats
      if (peerIds.length > 0) {
        return libp2p.ping(peerIds[0])
      }

      return 0
    }

    ping()
      .then((latency) => {
        setPeerStats({ ...peerStats, latency })
      })
      .catch((e) => {
        console.error(e, e?.error)
      })

    getConnectedPeers().then((peerIds) => {
      setPeerStats({ ...peerStats, peerIds, connected: true })
    })

    getConnections().then((connections) => {
      // If one of the connected peers matches the one in input we're connected
      setPeerStats({ ...peerStats, connections })
    })
  }, 5000)

  const getUniqueConnections = (connections: Connection[]) => {
    const uniqueConnections: Connection[] = []
    connections.forEach((conn) => {
      const exists = uniqueConnections.find(
        (c) => c.remotePeer.toString() === conn.remotePeer.toString(),
      )
      if (!exists) {
        uniqueConnections.push(conn)
      }
    })
    return uniqueConnections
  }

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
                <li className="">This PeerID: {libp2p.peerId.toString()}</li>
              </ul>


              <div className="my-4 inline-flex items-center text-xl">
                Connected:{' '}
                {peerStats.connected ? (
                  <CheckCircleIcon className="inline w-6 h-6 text-green-500" />
                ) : (
                  <XCircleIcon className="w-6 h-6 text-red-500" />
                )}
                <p className='mx-auto max-w-7xl px-2 sm:px-6 lg:px-8'>
                  {peerStats.latency > 0
                    ? `Latency of nearest peer: ${peerStats.latency} ms`
                    : null}
                </p>
              </div>
              <div>
                {peerStats.peerIds.length > 0 ? (
                  <>
                    <h3 className="text-xl">
                      {' '}
                      Connected peers ({peerStats.peerIds.length}) 👇
                    </h3>
                    <pre className="px-2">
                      {getUniqueConnections(peerStats.connections)
                        .map(
                          (conn) =>
                            `${conn.remotePeer.toString()} (${conn.remoteAddr.protoNames()})`,
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

export function Stats(
  stats: { name: string; stat: string }[] = [
    { name: 'Peer Ping Latency', stat: '' },
    { name: 'Peer Count', stat: '' },
  ],
) {
  return (
    <div>
      <h3 className="text-base font-semibold leading-6 text-gray-900">
        Last 30 days
      </h3>
      <dl className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-3">
        {stats.map((item) => (
          <div
            key={item.name}
            className="overflow-hidden rounded-lg bg-white px-4 py-5 shadow sm:p-6"
          >
            <dt className="truncate text-sm font-medium text-gray-500">
              {item.name}
            </dt>
            <dd className="mt-1 text-3xl font-semibold tracking-tight text-gray-900">
              {item.stat}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
