import Peer from "@/components/Peer"
import { ChatMessage } from "@/context/chat-ctx"
import React from "react"

interface Props extends ChatMessage { }

export const PeerMessage = ({ msg, fileObjectUrl, from, peerId }: Props) => {
  const msgref = React.useRef<HTMLLIElement>(null)

  return (
    <li ref={msgref} className="">

      <Peer peerId={peerId} me={from === 'me'} />
      <div
        className="relative -top-6 left-11 w-[calc(100%-2.5rem)] px-4 py-2 text-gray-700 rounded shadow bg-white"
      >
        <div className="block">
          {msg}
          <p>{fileObjectUrl ? <a href={fileObjectUrl} target="_blank"><b>Download</b></a> : ""}</p>
        </div>
      </div>
    </li>
  )
}

