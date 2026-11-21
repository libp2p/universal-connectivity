import React from 'react'
import { useRouter } from 'next/router'
import Spinner from './spinner'

interface Props {
  error?: string
}

export function Booting({ error }: Props) {
  const router = useRouter()
  const logoSrc = `${router.basePath || ''}/libp2p-logo.svg`

  return (
    <div className="grid h-screen place-items-center">
      <div className="text-center">
        <img src={logoSrc} alt="libp2p logo" height="156" width="156" className="text-white mx-auto mb-5" />
        <h2 className="text-3xl font-bold text-gray-900 mb-2">Initializing libp2p peer</h2>
        {!error && (
          <>
            <p className="text-lg text-gray-900 mb-2">Connecting to bootstrap nodes...</p>
            <Spinner />
          </>
        )}
        {error && error !== '' && <p className="text-lg text-gray-900">{error}</p>}
        {error && error === '' && <p className="text-lg text-gray-900">Unknown error</p>}
      </div>
    </div>
  )
}
