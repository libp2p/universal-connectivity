import Head from 'next/head'
import Nav from '@/components/nav'
import ChatContainer from '@/components/chat'
import ConnectionPanel from '@/components/connection-panel'
import { useState } from 'react'
import { useLibp2pContext } from '@/context/ctx'
import ConnectionInfoButton from '@/components/connection-info-button'

export default function Chat() {
  const [isConnectionPanelOpen, setIsConnectionPanelOpen] = useState(false)

  const handleOpenConnectionPanel = () => {
    setIsConnectionPanelOpen(true)
  }

  return (
    <>
      <Head>
        <title>Universal Connectivity</title>
        <meta name="description" content="universal connectivity" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>
      <main className="min-h-full flex flex-col">
        <Nav connectionInfoButton={<ConnectionInfoButton onClick={handleOpenConnectionPanel} />} />
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
