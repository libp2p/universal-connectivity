import { useLibp2pContext } from '@/context/ctx'
import React, { useCallback, useEffect, useState } from 'react'
import { Message } from '@libp2p/interface-pubsub'
import { CHAT_TOPIC } from '@/lib/constants'
import { PeerId } from 'kubo-rpc-client/dist/src/types'

interface ChatMessage {
  msg: string
  from: 'me' | 'other'
}
export default function ChatContainer() {
  const { libp2p } = useLibp2pContext()
  const [messages, setMessages] = useState<ChatMessage[]>([
    { msg: 'Hi', from: 'me' },
    { msg: 'Yo', from: 'other' },
    { msg: 'Wassup?', from: 'me' },
    { msg: 'all good!😊', from: 'other' },
  ])
  const [input, setInput] = useState<string>('')

  // Effect hook to subscribe to pubsub events and update the message state hook
  useEffect(() => {
    const messageCB = (message: CustomEvent<Message>) => {
      const { topic, data } = message.detail
      const msg = new TextDecoder().decode(data)
      console.log(`${topic}: ${msg}`)
      // Append new message
      setMessages([...messages, { msg, from: 'other' }])
    }

    libp2p.pubsub.addEventListener('message', messageCB)

    return () => {
      // Cleanup handlers 👇
      // libp2p.pubsub.unsubscribe(CHAT_TOPIC)
      libp2p.pubsub.removeEventListener('message', messageCB)
    }
  }, [libp2p, messages, setMessages])

  const sendMessage = useCallback(async () => {
    if (input === '') return

    const res = await libp2p.pubsub.publish(
      CHAT_TOPIC,
      new TextEncoder().encode(input),
    )
    setMessages([...messages, { msg: input, from: 'me' }])
    setInput('')
  }, [input, messages, setInput, libp2p])

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
              <span className="text-3xl">💁‍♀️💁</span>
              <span className="block ml-2 font-bold text-gray-600">
                Public Chat
              </span>
            </div>
            <div className="relative w-full p-6 overflow-y-auto h-[40rem]">
              <ul className="space-y-2">
                {/* messages start */}
                {messages.map(({ msg, from }, idx) => (
                  <li
                    key={idx}
                    className={`flex ${
                      from === 'me' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <div className="relative max-w-xl px-4 py-2 text-gray-700 rounded shadow">
                      <span className="block">{msg}</span>
                    </div>
                  </li>
                ))}
                {/* messages end */}
              </ul>
            </div>

            <div className="flex items-center justify-between w-full p-3 border-t border-gray-300">
              <button>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="w-6 h-6 text-gray-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </button>
              <button>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="w-5 h-5 text-gray-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
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
              <button>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="w-5 h-5 text-gray-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                  />
                </svg>
              </button>
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

export function RoomList() {
  return (
    <div className="border-r border-gray-300 lg:col-span-1">
      <div className="mx-3 my-3">
        <div className="relative text-gray-600">
          <span className="absolute inset-y-0 left-0 flex items-center pl-2">
            <svg
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              viewBox="0 0 24 24"
              className="w-6 h-6 text-gray-300"
            >
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
          </span>
          <input
            type="search"
            className="block w-full py-2 pl-10 bg-gray-100 rounded outline-none"
            name="search"
            placeholder="Search"
            required
          />
        </div>
      </div>

      <ul className="overflow-auto h-[32rem]">
        <h2 className="my-2 mb-2 ml-2 text-lg text-gray-600">Chats</h2>
        <li>
          <a className="flex items-center px-3 py-2 text-sm transition duration-150 ease-in-out border-b border-gray-300 cursor-pointer hover:bg-gray-100 focus:outline-none">
            <img
              className="object-cover w-10 h-10 rounded-full"
              src="https://github.com/2color.png"
              alt="username"
            />
            <div className="w-full pb-2">
              <div className="flex justify-between">
                <span className="block ml-2 font-semibold text-gray-600">
                  Daniel
                </span>
                <span className="block ml-2 text-sm text-gray-600">
                  25 minutes
                </span>
              </div>
              <span className="block ml-2 text-sm text-gray-600">bye</span>
            </div>
          </a>
          <a className="flex items-center px-3 py-2 text-sm transition duration-150 ease-in-out bg-gray-100 border-b border-gray-300 cursor-pointer focus:outline-none">
            <img
              className="object-cover w-10 h-10 rounded-full"
              src="https://github.com/achingbrain.png"
              alt="username"
            />
            <div className="w-full pb-2">
              <div className="flex justify-between">
                <span className="block ml-2 font-semibold text-gray-600">
                  Alex
                </span>
                <span className="block ml-2 text-sm text-gray-600">
                  50 minutes
                </span>
              </div>
              <span className="block ml-2 text-sm text-gray-600">
                Good night
              </span>
            </div>
          </a>
          <a className="flex items-center px-3 py-2 text-sm transition duration-150 ease-in-out border-b border-gray-300 cursor-pointer hover:bg-gray-100 focus:outline-none">
            <img
              className="object-cover w-10 h-10 rounded-full"
              src="https://github.com/hannahhoward.png"
              alt="username"
            />
            <div className="w-full pb-2">
              <div className="flex justify-between">
                <span className="block ml-2 font-semibold text-gray-600">
                  Hannah
                </span>
                <span className="block ml-2 text-sm text-gray-600">6 hour</span>
              </div>
              <span className="block ml-2 text-sm text-gray-600">
                Good Morning
              </span>
            </div>
          </a>
        </li>
      </ul>
    </div>
  )
}
