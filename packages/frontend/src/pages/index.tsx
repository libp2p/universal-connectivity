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

  type PeerProtoTuple = {
    peerId: string
    protocols: string[]
  }

  const getFormattedConnections = (connections: Connection[]): PeerProtoTuple[] => {
    const protoNames: Map<string, string[]> = new Map()

    connections.forEach((conn) => {
      const exists = protoNames.get(conn.remotePeer.toString())

      if (exists) {
        const namesToAdd = exists.filter(
          (name) => !conn.remoteAddr.protoNames().includes(name),
        )
        protoNames.set(conn.remotePeer.toString(), [...exists, ...namesToAdd])
      } else {
        protoNames.set(conn.remotePeer.toString(), conn.remoteAddr.protoNames())
      }
    })

    return [...protoNames.entries()].map(([peerId, protocols]) => ({
      peerId,
      protocols,
    }))

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
