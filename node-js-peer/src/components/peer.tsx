import React from 'react'
import { PeerId } from '@libp2p/interface'
import { useChatContext } from '../context/chat.js'
import { Text } from 'react-curse'
import { shortPeerId } from '../lib/short-peer-id.js'
import { peerColor } from '../lib/peer-color.js'

export interface PeerProps {
  peer: PeerId
  self: boolean
  children: any
}

export function Peer({ peer, self }: PeerProps) {
  const { directMessages } = useChatContext()
  const dmCount = directMessages[peer.toString()]?.length

  const color = peerColor(peer)
  return (
    <Text color={`#${color}`} block={true}>
      {shortPeerId(peer)} {self ? '(You)' : ''} {dmCount ? `(${dmCount})` : ''}
    </Text>
  )
}
