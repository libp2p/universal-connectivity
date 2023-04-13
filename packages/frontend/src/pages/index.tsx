import Head from 'next/head'
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/20/solid'
import Nav from '@/components/nav'
import { useLibp2pContext } from '@/context/ctx'
import { useInterval } from 'usehooks-ts'
import type { PeerId } from '@libp2p/interface-peer-id'
import type { Connection } from '@libp2p/interface-connection'
import { usePeerContext } from '../context/peer-ctx'
import { useEffect } from 'react'


export default function Home() {
  const { libp2p } = useLibp2pContext()
  const { peerStats, setPeerStats } = usePeerContext()

  useInterval(() => {

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
  }, 5000)

  useEffect(() => {
    const peerConnectedCB = (evt: CustomEvent<Connection>) => {
      const connection = evt.detail
      setPeerStats({ ...peerStats, peerIds: [...peerStats.peerIds, connection.remotePeer], connections: [...peerStats.connections, connection], connected: true })
    }

    libp2p.addEventListener('peer:connect', peerConnectedCB)

    return () => {
      libp2p.removeEventListener('peer:connect', peerConnectedCB)
    }
  }, [libp2p, peerStats, setPeerStats])

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
