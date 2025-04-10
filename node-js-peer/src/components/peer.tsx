import React from 'react'
import { PeerId } from '@libp2p/interface'
import { useChatContext } from '../context/chat.js'
import { Text } from 'react-curse'
import { shortPeerId } from '../lib/short-peer-id.js'
import { peerColor } from '../lib/peer-color.js'

export interface PeerProps {
  peer: PeerId
  self: boolean
  withName: boolean
  withUnread: boolean
  children: any
}

export function Peer({ peer, self, withName, withUnread }: PeerProps) {
  const { directMessages } = useChatContext()

  const color = peerColor(peer)

  return (
    <>
      <Text color={`#${color}`} block={true}>{shortPeerId(peer)}</Text>
    </>
  )
}
