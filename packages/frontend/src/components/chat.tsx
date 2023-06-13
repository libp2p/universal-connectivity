import { useLibp2pContext } from '@/context/ctx'
import React, { ChangeEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Message } from '@libp2p/interface-pubsub'
import { CHAT_TOPIC } from '@/lib/constants'
import { createIcon } from '@download/blockies'
import { ChatMessage, useChatContext } from '../context/chat-ctx'


interface MessageProps extends ChatMessage { }

function Message({ msg, from, peerId }: MessageProps) {
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
          <p className="italic text-gray-400">{peerId !== libp2p.peerId.toString() ? `from: ${peerId.slice(-4)}` : null} </p>
        </div>
      </div>
    </li>
  )
}

export default function ChatContainer() {
  const { libp2p } = useLibp2pContext()
  const { messageHistory, setMessageHistory } = useChatContext();
  const [input, setInput] = useState<string>('')
  const fileRef = useRef<HTMLInputElement>(null);

  // Effect hook to subscribe to pubsub events and update the message state hook
  useEffect(() => {
    const messageCB = (evt: CustomEvent<Message>) => {
      console.log('gossipsub console log', evt.detail)
      // FIXME: Why does 'from' not exist on type 'Message'?
      const { topic, data } = evt.detail
      const msg = new TextDecoder().decode(data)
      console.log(`${topic}: ${msg}`)

      // Append signed messages, otherwise discard
      if (evt.detail.type === 'signed') {
        setMessageHistory([...messageHistory, { msg, from: 'other', peerId: evt.detail.from.toString() }])
      }
    }

    libp2p.services.pubsub.addEventListener('message', messageCB)

    return () => {
      // Cleanup handlers 👇
      // libp2p.pubsub.unsubscribe(CHAT_TOPIC)
      libp2p.services.pubsub.removeEventListener('message', messageCB)
    }
  }, [libp2p, messageHistory, setMessageHistory])

  const sendMessage = useCallback(async () => {
    if (input === '') return

    console.log(
      'peers in gossip:',
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

    setMessageHistory([...messageHistory, { msg: input, from: 'me', peerId: myPeerId }])
    setInput('')
  }, [input, messageHistory, setInput, libp2p, setMessageHistory])

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
          const result = readerEvent.target?.result as ArrayBuffer;
          console.log(`READER_RESULT: ${result.byteLength} bytes`);
        };
      }
    },
    [],
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
              <span className="block ml-2 font-bold text-gray-600">
                Public Chat
              </span>
            </div>
            <div className="relative w-full p-6 overflow-y-auto h-[40rem] bg-gray-100">
              <ul className="space-y-2">
                {/* messages start */}
                {messageHistory.map(({ msg, from, peerId }, idx) => (
                  <Message key={idx} msg={msg} from={from} peerId={peerId} />
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
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </button>

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
              <button>
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
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
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
