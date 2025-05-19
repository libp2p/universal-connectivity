import { ServerIcon } from '@heroicons/react/24/outline'
import React from 'react'

interface ConnectionInfoButtonProps {
  onClick: () => void
}

export default function ConnectionInfoButton({ onClick }: ConnectionInfoButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md bg-indigo-600 py-1.5 px-2 sm:px-3 text-xs sm:text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 flex items-center"
    >
      <ServerIcon className="h-4 w-4 sm:h-5 sm:w-5 mr-1 sm:mr-2" aria-hidden="true" />
      <span className="hidden sm:inline">libp2p node info</span>
      <span className="sm:hidden">Node</span>
    </button>
  )
}
