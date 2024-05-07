import { useLibp2pContext } from '@/context/ctx'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import type { Message } from '@libp2p/interface'
import { CHAT_FILE_TOPIC, CHAT_TOPIC, FILE_EXCHANGE_PROTOCOL } from '@/lib/constants'
import { createIcon } from '@download/blockies'
import { ChatFile, ChatMessage, useChatContext } from '../context/chat-ctx'
import { v4 as uuidv4 } from 'uuid';
import { pipe } from 'it-pipe'
import map from 'it-map'
import { fromString as uint8ArrayFromString } from 'uint8arrays/from-string'
import { toString as uint8ArrayToString } from 'uint8arrays/to-string'
import * as lp from 'it-length-prefixed'
import { MessageComponent } from './message'

interface MessageProps extends ChatMessage { }



export default function ChatContainer() {
  const { libp2p } = useLibp2pContext()
  const { messageHistory, setMessageHistory, files, setFiles } = useChatContext();
  const [input, setInput] = useState<string>('')
  const fileRef = useRef<HTMLInputElement>(null);

  const sendMessage = useCallback(async () => {
    if (input === '') return

    console.log(
      `peers in gossip for topic ${CHAT_TOPIC}:`,
      libp2p.services.pubsub.getSubscribers(CHAT_TOPIC).toString(),
    )

    const res = await libp2p.services.pubsub.publish(
      CHAT_TOPIC,
      new TextEncoder().encode(input),
    )
    console.log(
      'sent message to: ',
      res.recipients.map((peerId) => peerId.toString()),
    )

    const myPeerId = libp2p.peerId.toString()

    setMessageHistory([...messageHistory, { msg: input, fileObjectUrl: undefined, from: 'me', peerId: myPeerId }])
    setInput('')
  }, [input, messageHistory, setInput, libp2p, setMessageHistory])

  const sendFile = useCallback(async (readerEvent: ProgressEvent<FileReader>) => {
    const fileBody = readerEvent.target?.result as ArrayBuffer;

    const myPeerId = libp2p.peerId.toString()
    const file: ChatFile = {
      id: uuidv4(),
      body: new Uint8Array(fileBody),
      sender: myPeerId,
    }
    setFiles(files.set(file.id, file))

    console.log(
      `peers in gossip for topic ${CHAT_FILE_TOPIC}:`,
      libp2p.services.pubsub.getSubscribers(CHAT_FILE_TOPIC).toString(),
    )

    const res = await libp2p.services.pubsub.publish(
      CHAT_FILE_TOPIC,
      new TextEncoder().encode(file.id)
    )
    console.log(
      'sent file to: ',
      res.recipients.map((peerId) => peerId.toString()),
    )

    const msg: ChatMessage = {
      msg: newChatFileMessage(file.id, file.body),
      fileObjectUrl: window.URL.createObjectURL(new Blob([file.body])),
      from: 'me',
      peerId: myPeerId,
    }
    setMessageHistory([...messageHistory, msg])
  }, [messageHistory, libp2p, setMessageHistory, files, setFiles])

  const newChatFileMessage = (id: string, body: Uint8Array) => {
    return `File: ${id} (${body.length} bytes)`
  }

  const handleKeyUp = useCallback(
    async (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key !== 'Enter') {
        return
      }
      sendMessage()
    },
    [sendMessage],
  )

  const handleSend = useCallback(
    async (e: React.MouseEvent<HTMLButtonElement>) => {
      sendMessage()
    },
    [sendMessage],
  )

  const handleInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setInput(e.target.value)
    },
    [setInput],
  )

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        const reader = new FileReader();
        reader.readAsArrayBuffer(e.target.files[0]);
        reader.onload = (readerEvent) => {
          sendFile(readerEvent)
        };
      }
    },
    [sendFile],
  )

  const handleFileSend = useCallback(
    async (_e: React.MouseEvent<HTMLButtonElement>) => {
      fileRef?.current?.click();
    },
    [fileRef],
  )

  return (
    <div className="container mx-auto">
      <div className="min-w-full border rounded lg:grid lg:grid-cols-3">
        {/* <RoomList /> */}
        <div className="lg:col-span-3 lg:block">
          <div className="w-full">
            <div className="relative flex items-center p-3 border-b border-gray-300">
              {/* disable
              <img
                className="object-cover w-10 h-10 rounded-full"
                src="https://github.com/achingbrain.png"
                alt="username"
              />
              <span className="absolute w-3 h-3 bg-green-600 rounded-full left-10 top-3"></span> */}
              <span className="text-3xl">💁🏽‍♀️💁🏿‍♂️</span>
              <span className="block ml-2 font-bold text-gray-600">Public Chat</span>
            </div>
            <div className="relative w-full flex flex-col-reverse p-6 overflow-y-auto h-[40rem] bg-gray-100">
              <ul className="space-y-2">
                {/* messages start */}
                {messageHistory.map(({ msg, fileObjectUrl, from, peerId }, idx) => (
                  <MessageComponent
                    key={idx}
                    msg={msg}
                    fileObjectUrl={fileObjectUrl}
                    from={from}
                    peerId={peerId}
                  />
                ))}
                {/* messages end */}
              </ul>
            </div>

            <div className="flex items-center justify-between w-full p-3 border-t border-gray-300">
              <input ref={fileRef} className="hidden" type="file" onChange={handleFileInput} />
              <button onClick={handleFileSend}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="w-5 h-5 text-gray-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                  />
                </svg>
              </button>

              <input
                value={input}
                onKeyUp={handleKeyUp}
                onChange={handleInput}
                type="text"
                placeholder="Message"
                className="block w-full py-2 pl-4 mx-3 bg-gray-100 rounded-full outline-none focus:text-gray-700"
                name="message"
                required
              />
              <button onClick={handleSend} type="submit">
                <svg
                  className="w-5 h-5 text-gray-500 origin-center transform rotate-90"
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
