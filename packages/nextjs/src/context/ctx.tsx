import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react'

import type { Libp2p } from 'libp2p'
import { startLibp2p } from '../lib/libp2p'

// 👇 The context type will be avilable "anywhere" in the app
interface Libp2pContextInterface {
  libp2p: Libp2p
}
export const libp2pContext = createContext<Libp2pContextInterface>({
  // @ts-ignore to avoid having to check isn't undefined everywhere. Can't be undefined because children are conditionally rendered
  libp2p: undefined,
})

interface WrapperProps {
  children?: ReactNode
}

export function AppWrapper({ children }: WrapperProps) {
  const [libp2p, setLibp2p] = useState<Libp2p>()

  useEffect(() => {
    const init = async () => {
      try {
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
      {children}
    </libp2pContext.Provider>
  )
}

export function useLibp2pContext() {
  return useContext(libp2pContext)
}
