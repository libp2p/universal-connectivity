import React, { useEffect } from 'react'
import Peer from '@/components/Peer'
import { ChatMessage, useChatContext } from '@/context/chat-ctx'

interface Props extends ChatMessage {
  dm: boolean
}

export const PeerMessage = ({
  msgId,
  msg,
  fileObjectUrl,
  from,
  peerId,
  read,
  dm,
}: Props) => {
  const { messageHistory, setMessageHistory, dmMessages, setDMMessages } =
    useChatContext()

  useEffect(() => {
    console.log('Effect running', { dm, peerId, msgId, read })

    if (read) return // Exit if already read, no update needed

    const updateMessages = (messages: ChatMessage[]) =>
      messages.map((m) => (m.msgId === msgId ? { ...m, read: true } : m))

    if (dm) {
      console.log('in dms')
      const updatedDMs = dmMessages[peerId]

      if (updatedDMs.some((m) => m.msgId === msgId && !m.read)) {
        console.log('Updating DMs for', peerId)

        setDMMessages((prev) => ({
          ...prev,
          [peerId]: updateMessages(updatedDMs),
        }))
      }
    } else {
      if (messageHistory.some((m) => m.msgId === msgId && !m.read)) {
        console.log('Updating public msg')
        setMessageHistory((prev) => updateMessages(prev))
      }
    }
  }, [
    dm,
    dmMessages,
    messageHistory,
    msgId,
    peerId,
    read,
    setDMMessages,
    setMessageHistory,
  ])

  return (
    <li>
      <Peer peerId={peerId} me={from === 'me'} />
      <div className="relative -top-6 left-11 w-[calc(100%-2.5rem)] px-4 py-2 text-gray-700 rounded shadow bg-white">
        <div className="block">
          {msg}
          <p>
            {fileObjectUrl ? (
              <a href={fileObjectUrl} target="_blank" rel="noreferrer">
                <b>Download</b>
              </a>
            ) : (
              ''
            )}
          </p>
        </div>
      </div>
    </li>
  )
}
