import { useEffect } from 'react'
import { useLibp2pContext } from '@/context/ctx'
import { AutoDialerMaxConnections, CHAT_TOPIC } from '@/lib/constants/'

// AutoDialer attempts to connect to peers it discovers via pubsub messages
export const AutoDialer = () => {
  const { libp2p } = useLibp2pContext()

  useEffect(() => {
    if (!libp2p) {
      return
    }

    const pubsubMsg = async (evt: CustomEvent<any>) => {
      if (!evt || !evt.detail || !evt.detail.from || !evt.detail.topic) {
        console.warn('invalid pubsub message', evt)
        return
      }

      if (evt.detail.topic !== CHAT_TOPIC) {
        console.debug(
          `skipping non-${CHAT_TOPIC} pubsub messages (${evt.detail.topic}, ${evt.detail.from}, ${evt}`,
        )
        return
      }

      console.debug(`received ${CHAT_TOPIC} pubsub message`, evt.detail)

      try {
        if (!(await libp2p.peerStore.has(evt.detail.from))) {
          console.log('undiscovered peer', evt.detail.from.toString())

          if (libp2p.getConnections().length < AutoDialerMaxConnections) {
            await libp2p.dial(evt.detail.from)
          } else {
            console.debug('max connections for AutoDialer reached')
          }
        }
      } catch (e: any) {
        console.log('autodialer error', e)
      }
    }

    libp2p.services.pubsub.addEventListener('message', pubsubMsg)

    return () => {
      if (libp2p && libp2p.services && libp2p.services.pubsub) {
        libp2p.services.pubsub.removeEventListener('message', pubsubMsg)
      }
    }
  }, [libp2p])

  return <></>
}
