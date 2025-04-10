import { useLibp2pContext } from '../context/index.js'
import { CHAT_TOPIC } from '../constants.js'
import React, { useEffect, useState } from 'react'
import { Peer } from './peer.js'
import type { PeerId } from '@libp2p/interface'
import { Text, Frame, View } from 'react-curse'
import { PositionProps } from '../index.js'

export function PeerList(props: PositionProps) {
  const { libp2p } = useLibp2pContext()
  const [ subscribers, setSubscribers ] = useState<PeerId[]>([])

  useEffect(() => {
    const onSubscriptionChange = () => {
      setSubscribers(libp2p.services.pubsub.getSubscribers(CHAT_TOPIC))
    }
    onSubscriptionChange()

    libp2p.services.pubsub.addEventListener('subscription-change', onSubscriptionChange)

    return () => {
      libp2p.services.pubsub.removeEventListener('subscription-change', onSubscriptionChange)
    }
  }, [libp2p, setSubscribers])

  return (
    <>
      <Frame absolute={true} {...props}>
        <View>{
          subscribers.map((p) => (
            <Peer
              key={p.toString()}
              peer={p}
              self={false}
              withName={true}
              withUnread={true}
              children={[]}
            />
          ))
        }</View>
      </Frame>
      <Text absolute={true} x={props.x + 2} y={props.y}>Topic Peers ({subscribers.length})</Text>
    </>
  )
}
