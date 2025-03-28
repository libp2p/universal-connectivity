import Head from 'next/head'
import Nav from '@/components/nav'
import PixelArtEditor from '@/components/pixel-art-editor'
import ConnectionPanel from '@/components/connection-panel'
import { useState } from 'react'
import ConnectionInfoButton from '@/components/connection-info-button'

export default function PixelArt() {
  const [isConnectionPanelOpen, setIsConnectionPanelOpen] = useState(false)

  const handleOpenConnectionPanel = () => {
    setIsConnectionPanelOpen(true)
  }

  return (
    <>
      <Head>
        <title>Pixel Art - Universal Connectivity</title>
        <meta name="description" content="Collaborative pixel art with libp2p" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>
      <main className="min-h-full flex flex-col">
        <Nav connectionInfoButton={<ConnectionInfoButton onClick={handleOpenConnectionPanel} />} />
        <div className="flex-1 mx-auto w-full max-w-7xl px-0 sm:px-2 pt-0 pb-2 lg:px-8">
          <div className="bg-white shadow-sm rounded-lg overflow-hidden border border-gray-200">
            <PixelArtEditor />
          </div>
        </div>
      </main>
      <ConnectionPanel isOpen={isConnectionPanelOpen} onClose={() => setIsConnectionPanelOpen(false)} />
    </>
  )
}
