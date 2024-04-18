import { useLibp2pContext } from "@/context/ctx"
import { CHAT_TOPIC } from "@/lib/constants"
import { shortPeerId } from "@/lib/peers"

export const PubsubSubscribers = () => {
  const { libp2p } = useLibp2pContext()

  const subs = libp2p.services.pubsub.getSubscribers(CHAT_TOPIC)

  return (
    <>
      <h3 className="text-xl">Pubsub Subscribers ({subs.length})</h3>
      {subs.map((sub) => (
        <div key={sub.toString()}>
          <div className="px-2">{shortPeerId(sub.toString())}</div>
        </div>
      ))}
    </>
  )
}
