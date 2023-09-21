import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react'

import type { Libp2p } from 'libp2p'
import { startLibp2p } from '../lib/libp2p'
import { ChatProvider } from './chat-ctx'
import { PeerProvider } from './peer-ctx'
import { ListenAddressesProvider } from './listen-addresses-ctx'
import { PubSub } from '@libp2p/interface-pubsub'

// 👇 The context type will be avilable "anywhere" in the app
interface Libp2pContextInterface {
  libp2p: Libp2p<{ pubsub: PubSub }>
}
export const libp2pContext = createContext<Libp2pContextInterface>({
  // @ts-ignore to avoid having to check isn't undefined everywhere. Can't be undefined because children are conditionally rendered
  libp2p: undefined,
})

interface WrapperProps {
  children?: ReactNode
}
let loaded = false
export function AppWrapper({ children }: WrapperProps) {
  const [libp2p, setLibp2p] = useState<Libp2p<{ pubsub: PubSub }>>()

  useEffect(() => {
    const init = async () => {
      if (loaded) return
      try {
        loaded = true
        const libp2p = await startLibp2p()

        // @ts-ignore
        window.libp2p = libp2p

        setLibp2p(libp2p)
      } catch (e) {
        console.error('failed to start libp2p', e)
      }
    }

    init()
  }, [])

  if (!libp2p) {
    return (
      <div>
        <h2>Initializing libp2p peer...</h2>
      </div>
    )
  }

  return (
    <libp2pContext.Provider value={{ libp2p }}>
      <ChatProvider>
        <PeerProvider>
          <ListenAddressesProvider>
            {children}
          </ListenAddressesProvider>
        </PeerProvider>
      </ChatProvider>
    </libp2pContext.Provider>
  )
}

export function useLibp2pContext() {
  return useContext(libp2pContext)
}
