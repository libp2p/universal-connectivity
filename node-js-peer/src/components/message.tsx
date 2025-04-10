import React from 'react'
import { Text } from 'react-curse'
import { useLibp2pContext } from '../context/index.js'
import { ChatMessage } from '../context/chat.js'
import { useMarkAsRead } from '../hooks/mark-as-read.js'
import { peerIdFromString } from '@libp2p/peer-id'
import { peerColor } from '../lib/peer-color.js'

interface Props extends ChatMessage {
  dm: boolean
  children: any
}

export const Message = ({ msgId, msg, peerId, read, dm, receivedAt }: Props) => {
  const { libp2p } = useLibp2pContext()

  const p = peerIdFromString(peerId)

  const isSelf = libp2p.peerId.equals(p)
  const timestamp = new Date(receivedAt).toLocaleString()

  useMarkAsRead(msgId, peerId, read, dm)

  const color = isSelf ? undefined : `#${peerColor(p)}`

  return (
    <>
      <Text color={color} block={true}>{timestamp} - {peerId.substring(peerId.length - 7)} - {msg}</Text>
    </>
  )
}
