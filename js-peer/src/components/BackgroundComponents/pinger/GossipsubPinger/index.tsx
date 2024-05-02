import { useEffect } from 'react'
import { useLibp2pContext } from '@/context/ctx'
import { CHAT_TOPIC } from '@/lib/constants/'

const GOSSIP_PING_INTERVAL_MS = 5000

// Gossipsub Pinger - periodically sends a message to the chat topic
// Noisy but useful for debugging
export const GossipsubPinger = () => {
  const { libp2p } = useLibp2pContext()

  useEffect(() => {
    const interval = setInterval(() => {
      if (!libp2p) {
        return
      }

      const init = async () => {
        const pingMsg = new TextEncoder().encode('ping')

        const res = await libp2p.services.pubsub.publish(CHAT_TOPIC, pingMsg)

        // eslint-disable-next-line no-console
        console.log(`sending gossipsub ping to ${CHAT_TOPIC}`, res)
      }

      init()
    }, GOSSIP_PING_INTERVAL_MS)

    return () => {
      clearInterval(interval)
    }
  }, [libp2p])

  return <></>
}
