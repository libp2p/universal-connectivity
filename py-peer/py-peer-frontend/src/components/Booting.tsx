import Spinner from './Spinner'

export default function Booting({ error }: { error?: string }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 gap-4 px-4">
      <img src="/libp2p-logo.svg" alt="libp2p" className="h-16 w-16" />
      <h1 className="text-xl font-semibold text-gray-700">Universal Connectivity – py-peer</h1>
      {error ? (
        <div className="max-w-md rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700 text-center">
          {error}
        </div>
      ) : (
        <div className="flex items-center gap-2 text-gray-500 text-sm">
          <Spinner className="h-4 w-4" />
          Connecting to py-peer API on localhost:8765…
        </div>
      )}
    </div>
  )
}
