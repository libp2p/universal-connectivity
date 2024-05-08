import { useLibp2pContext } from '@/context/ctx'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { ChatMessage } from '@/context/chat-ctx'
import Blockies from 'react-18-blockies'

interface MessageProps extends ChatMessage {}

export function MessageComponent({ msg, fileObjectUrl, from, peerId }: MessageProps) {
  const { libp2p } = useLibp2pContext()

  return (
    <li className={`flex ${from === 'me' && 'flex-row-reverse'} gap-2`}>
      <Blockies seed={peerId} size={15} scale={3} className="rounded max-h-10 max-w-10" />
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
        </div>
      </div>
    </li>
  )
}
