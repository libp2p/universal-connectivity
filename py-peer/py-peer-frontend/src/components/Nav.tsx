import ConnectionInfoButton from './ConnectionInfoButton'

interface NavProps {
  onOpenPanel: () => void
}

export default function Nav({ onOpenPanel }: NavProps) {
  return (
    <nav className="border-b border-gray-200 bg-white sticky top-0 z-10">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 justify-between items-center">
          <div className="flex items-center gap-3">
            <img src="/libp2p-logo.svg" alt="libp2p" className="h-8 w-8" />
            <span className="text-lg font-semibold text-gray-900 hidden sm:block">
              Universal Connectivity
            </span>
            <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700">
              py-peer
            </span>
          </div>

          <div className="flex items-center gap-3">
            <a
              href="https://github.com/libp2p/universal-connectivity"
              target="_blank"
              rel="noreferrer"
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Source
            </a>
            <button
              onClick={onOpenPanel}
              className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 transition"
            >
              Connection Info
            </button>
            <ConnectionInfoButton />
          </div>
        </div>
      </div>
    </nav>
  )
}
