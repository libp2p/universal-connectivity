import React, { useEffect } from 'react'
import { useLibp2pContext } from '@/context/ctx'
import { ChatMessage, useChatContext } from '@/context/chat-ctx'
import { Peer } from './peer'
import { peerIdFromString } from '@libp2p/peer-id'

interface Props extends ChatMessage {
  dm: boolean
}

export const Message = ({ msgId, msg, fileObjectUrl, peerId, read, dm, receivedAt }: Props) => {
  const { messageHistory, setMessageHistory, directMessages, setDirectMessages } = useChatContext()
  const { libp2p } = useLibp2pContext()

  const isSelf: boolean = libp2p.peerId.equals(peerId)

  useEffect(() => {
    if (read) {
      return
    }

    const updateMessages = (messages: ChatMessage[]) =>
      messages.map((m) => (m.msgId === msgId ? { ...m, read: true } : m))

    if (dm) {
      const updatedDMs = directMessages[peerId]

      if (updatedDMs.some((m) => m.msgId === msgId && !m.read)) {
        setDirectMessages((prev) => ({
          ...prev,
          [peerId]: updateMessages(updatedDMs),
        }))
      }
    } else {
      if (messageHistory.some((m) => m.msgId === msgId && !m.read)) {
        setMessageHistory((prev) => updateMessages(prev))
      }
    }
  }, [dm, directMessages, messageHistory, msgId, peerId, read, setDirectMessages, setMessageHistory])

  const timestamp = new Date(receivedAt).toLocaleString()

  return (
    <li className={`flex ${isSelf && 'flex-row-reverse'} gap-2`}>
      <Peer
        key={peerId}
        peer={peerIdFromString(peerId)}
        self={isSelf}
        withName={false}
        withUnread={false}
      />
      <div className="flex relative max-w-xl px-4 py-2 text-gray-700 rounded shadow bg-white">
        <div className="block">
          {msg}
          <p>
            {fileObjectUrl ? (
              <a href={fileObjectUrl} target="_blank">
                <b>Download</b>
              </a>
            ) : (
              ''
            )}
          </p>
          <p className="italic text-gray-400">
            {peerId !== libp2p.peerId.toString() ? `from: ${peerId.slice(-4)}` : null}{' '}
          </p>
          <span className="relative pl-1 text-xs text-slate-400">{timestamp}</span>
        </div>
      </div>
    </li>
  )
}
