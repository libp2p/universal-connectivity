import React, { useEffect } from 'react'
import { useLibp2pContext } from '@/context/ctx'
import { ChatMessage, useChatContext } from '@/context/chat-ctx'
import { PeerWrapper } from './peer'
import { peerIdFromString } from '@libp2p/peer-id'
import { useMarkAsRead } from '@/hooks/useMarkAsRead'

interface Props extends ChatMessage {
  dm: boolean
}

export const Message = ({ msgId, msg, fileObjectUrl, peerId, read, dm, receivedAt }: Props) => {
  const { libp2p } = useLibp2pContext()
  const { initiateVideoCall, activeVideoCall } = useChatContext()

  const isSelf: boolean = libp2p.peerId.equals(peerId)
  const timestamp = new Date(receivedAt).toLocaleString()

  useMarkAsRead(msgId, peerId, read, dm)

  const handleVideoCall = async () => {
    try {
      await initiateVideoCall(peerId)
    } catch (err) {
      console.error('Failed to start video call:', err)
    }
  }

  return (
    <li className={`flex ${isSelf && 'flex-row-reverse'} gap-2`}>
      <PeerWrapper key={peerId} peer={peerIdFromString(peerId)} self={isSelf} withName={false} withUnread={false} />
      <div className="flex relative max-w-xl px-4 py-2 text-gray-700 rounded shadow bg-white">
        <div className="block">
          {msg}
          <div className="flex items-center gap-2 mt-1">
            {fileObjectUrl && (
              <a href={fileObjectUrl} target="_blank" className="text-blue-500 hover:text-blue-700">
                <b>Download</b>
              </a>
            )}
            {!isSelf && dm && (
              <button
                onClick={handleVideoCall}
                disabled={activeVideoCall !== null}
                className={`text-sm px-2 py-1 rounded ${activeVideoCall === null
                  ? 'bg-blue-500 text-white hover:bg-blue-600'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  }`}
              >
                {activeVideoCall === null ? 'Video Call' : 'In Call'}
              </button>
            )}
          </div>
          <p className="italic text-gray-400 mt-1">
            {!dm && peerId !== libp2p.peerId.toString() ? `from: ${peerId.slice(-4)}` : null}{' '}
          </p>
          <span className="relative pl-1 text-xs text-slate-400">{timestamp}</span>
        </div>
      </div>
    </li>
  )
}
