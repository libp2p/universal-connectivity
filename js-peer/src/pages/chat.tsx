import Head from 'next/head'
import Nav from '@/components/nav'
import ChatContainer from '@/components/chat'
import ConnectionPanel from '@/components/connection-panel'
import { useState } from 'react'
import { useLibp2pContext } from '@/context/ctx'
import { ServerIcon } from '@heroicons/react/24/outline'

export default function Chat() {
  const [isConnectionPanelOpen, setIsConnectionPanelOpen] = useState(false)
  const { libp2p } = useLibp2pContext()

  const connectionInfoButton = (
    <button
      type="button"
      onClick={() => setIsConnectionPanelOpen(true)}
      className="rounded-md bg-indigo-600 py-1.5 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 flex items-center"
    >
      <ServerIcon className="h-5 w-5 mr-2" aria-hidden="true" />
      libp2p node info
    </button>
  )

  return (
    <>
      <Head>
        <title>Universal Connectivity</title>
        <meta name="description" content="universal connectivity" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>
      <main className="min-h-full flex flex-col">
        <Nav connectionInfoButton={connectionInfoButton} />
        <div className="flex-1 mx-auto w-full max-w-7xl px-0 sm:px-2 pt-0 pb-2 lg:px-8">
          <div className="bg-white shadow-sm rounded-lg overflow-hidden border border-gray-200">
            <ChatContainer />
          </div>
        </div>
      </main>
      <ConnectionPanel isOpen={isConnectionPanelOpen} onClose={() => setIsConnectionPanelOpen(false)} />
    </>
  )
}
