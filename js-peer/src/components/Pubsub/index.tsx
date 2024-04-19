import { useLibp2pContext } from "@/context/ctx"
import { useEffect, useState } from "react"
import { PeerId } from '@libp2p/interface'
import Peer from "../Peer"
import { CHAT_TOPIC } from "@/lib/constants"

const UPDATE_INTERVAL = 1000

export const PubsubSubscribers = () => {
  const { libp2p } = useLibp2pContext()
  const [subs, setSubs] = useState<PeerId[]>([])

  useEffect(() => {
    const interval = setInterval(() => {
      if (!libp2p) {
        return
      }

      const subs = libp2p.services.pubsub.getSubscribers(CHAT_TOPIC)
      setSubs(subs)
    }, UPDATE_INTERVAL)

    return () => {
      clearInterval(interval)
    }
  }, [libp2p, subs, setSubs])

  return (
    <>
      <h3 className="font-bold text-gray-600">Who&apos;s Online ({subs.length + 1})</h3>
      <div className="p-2">
        <Peer peerId={libp2p.peerId.toString()} me />
      </div>
      {subs.map((sub) => (
        <div key={sub.toString()} className="p-2">
          <Peer peerId={sub.toString()} />
        </div>
      ))}
    </>
  )
}
