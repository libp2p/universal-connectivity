import { useState } from 'react'
import { PyPeerProvider, usePyPeer } from './context/PyPeerContext'
import Nav from './components/Nav'
import Chat from './components/Chat'
import ConnectionPanel from './components/ConnectionPanel'
import Booting from './components/Booting'
import LibP2PAssistant from './components/LibP2PAssistant'

function AppInner() {
  const { loading, error } = usePyPeer()
  const [panelOpen, setPanelOpen] = useState(false)

  if (loading || error) {
    return <Booting error={error} />
  }

  return (
    <div className="flex flex-col h-full bg-white">
      <Nav onOpenPanel={() => setPanelOpen(true)} />

      {/* Main layout */}
      <main className="flex-1 min-h-0 flex flex-col mx-auto w-full max-w-7xl px-0 sm:px-2 pb-2 pt-2 lg:px-8">
        <div className="flex flex-1 min-h-0 rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          <Chat />
        </div>
      </main>

      <ConnectionPanel isOpen={panelOpen} onClose={() => setPanelOpen(false)} />
      <LibP2PAssistant />
    </div>
  )
}

export default function App() {
  return (
    <PyPeerProvider>
      <AppInner />
    </PyPeerProvider>
  )
}
