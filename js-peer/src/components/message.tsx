import { useLibp2pContext } from '@/context/ctx'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createIcon } from '@download/blockies'
import { ChatMessage } from '@/context/chat-ctx'


interface MessageProps extends ChatMessage { }


export function MessageComponent({ msg, fileObjectUrl, from, peerId }: MessageProps) {
  const msgref = React.useRef<HTMLLIElement>(null)
  const { libp2p } = useLibp2pContext()


  useEffect(() => {
    const icon = createIcon({
      seed: peerId,
      size: 15,
      scale: 3,
    })
    icon.className = 'rounded mr-2 max-h-10 max-w-10'
    const childrenCount = msgref.current?.childElementCount
    // Prevent inserting an icon more than once.
    if (childrenCount && childrenCount < 2) {
      msgref.current?.insertBefore(icon, msgref.current?.firstChild)
    }
  }, [peerId])

  return (
    <li ref={msgref} className={`flex ${from === 'me' ? 'justify-end' : 'justify-start'}`}>
      <div

        className="flex relative max-w-xl px-4 py-2 text-gray-700 rounded shadow bg-white"
      >
        <div className="block">
          {msg}
          <p>{fileObjectUrl ? <a href={fileObjectUrl} target="_blank"><b>Download</b></a> : ""}</p>
          <p className="italic text-gray-400">{peerId !== libp2p.peerId.toString() ? `from: ${peerId.slice(-4)}` : null} </p>
        </div>
      </div>
    </li>
  )
}