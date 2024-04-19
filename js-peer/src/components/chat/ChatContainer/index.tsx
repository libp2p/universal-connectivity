import { useLibp2pContext } from '@/context/ctx'
import React, { useEffect } from 'react'
import type { Message } from '@libp2p/interface'
import { CHAT_FILE_TOPIC, CHAT_TOPIC, FILE_EXCHANGE_PROTOCOL } from '@/lib/constants/'
import { ChatMessage, useChatContext } from '../../../context/chat-ctx'
import { ChatFile, useFileChatContext } from '@/context/file-ctx'
import { pipe } from 'it-pipe'
import map from 'it-map'
import { fromString as uint8ArrayFromString } from 'uint8arrays/from-string'
import { toString as uint8ArrayToString } from 'uint8arrays/to-string'
import * as lp from 'it-length-prefixed'
import { PeerMessage } from '../PeerMessage'
import { InputBar } from '../InputBar'
import { newChatFileMessage } from '@/lib/chat'

export default function ChatContainer() {
  const { libp2p } = useLibp2pContext()
  const { messageHistory, setMessageHistory } = useChatContext();
  const { files, setFiles } = useFileChatContext();

  // Effect hook to subscribe to pubsub events and update the message state hook
  useEffect(() => {
    const messageCB = async (evt: CustomEvent<Message>) => {
      console.log('gossipsub console log', evt.detail)
      // FIXME: Why does 'from' not exist on type 'Message'?
      const { topic, data } = evt.detail

      switch (topic) {
        case CHAT_TOPIC: {
          chatMessageCB(evt, topic, data)
          break
        }
        case CHAT_FILE_TOPIC: {
          chatFileMessageCB(evt, topic, data)
          break
        }
        default: {
          console.log(`Unexpected gossipsub topic: ${topic}`)
        }
      }
    }

    const messageCBWrapper = (evt: Event) => {
      const customEvent = evt as CustomEvent<Message>;
      (async () => messageCB(customEvent))();
    };

    const chatMessageCB = (evt: CustomEvent<Message>, topic: string, data: Uint8Array) => {
      const msg = new TextDecoder().decode(data)
      console.log(`${topic}: ${msg}`)

      // Append signed messages, otherwise discard
      if (evt.detail.type === 'signed') {
        setMessageHistory([...messageHistory, { msg, fileObjectUrl: undefined, from: 'other', peerId: evt.detail.from.toString() }])
      }
    }

    const chatFileMessageCB = async (evt: CustomEvent<Message>, topic: string, data: Uint8Array) => {
      const fileId = new TextDecoder().decode(data)

      // if the message isn't signed, discard it.
      if (evt.detail.type !== 'signed') {
        return
      }
      const senderPeerId = evt.detail.from;

      try {
        const stream = await libp2p.dialProtocol(senderPeerId, FILE_EXCHANGE_PROTOCOL)
        await pipe(
          [uint8ArrayFromString(fileId)],
          (source) => lp.encode(source),
          stream,
          (source) => lp.decode(source),
          async function(source) {
            for await (const data of source) {
              const body: Uint8Array = data.subarray()
              console.log(`request_response: response received: size:${body.length}`)

              const msg: ChatMessage = {
                msg: newChatFileMessage(fileId, body),
                fileObjectUrl: window.URL.createObjectURL(new Blob([body])),
                from: 'other',
                peerId: senderPeerId.toString(),
              }
              setMessageHistory([...messageHistory, msg])
            }
          }
        )
      } catch (e) {
        console.error(e)
      }
    }

    libp2p.services.pubsub.addEventListener('message', messageCBWrapper)

    libp2p.handle(FILE_EXCHANGE_PROTOCOL, ({ stream }) => {
      pipe(
        stream.source,
        (source) => lp.decode(source),
        (source) => map(source, async (msg) => {
          const fileId = uint8ArrayToString(msg.subarray())
          const file = files.get(fileId)!
          return file.body
        }),
        (source) => lp.encode(source),
        stream.sink,
      )
    })

    return () => {
      (async () => {
        // Cleanup handlers 👇
        // libp2p.services.pubsub.unsubscribe(CHAT_TOPIC)
        // libp2p.services.pubsub.unsubscribe(CHAT_FILE_TOPIC)
        libp2p.services.pubsub.removeEventListener('message', messageCBWrapper)
        await libp2p.unhandle(FILE_EXCHANGE_PROTOCOL)
      })();
    }
  }, [libp2p, messageHistory, setMessageHistory, files])

  return (
    <div className="container mx-auto">
      <div className="min-w-full border rounded lg:grid lg:grid-cols-3">
        <div className="lg:col-span-3 lg:block">
          <div className="w-full">
            <div className="relative flex items-center p-3 border-b border-gray-300">
              <span className="text-3xl">💁🏽‍♀️💁🏿‍♂️</span>
              <span className="block ml-2 font-bold text-gray-600">
                Public Chat
              </span>
            </div>
            <div className="relative w-full flex flex-col-reverse p-6 overflow-y-auto h-[40rem] bg-gray-100">
              <ul className="space-y-2">
                {messageHistory.map(({ msg, fileObjectUrl, from, peerId }, idx) => (
                  <PeerMessage key={idx} msg={msg} fileObjectUrl={fileObjectUrl} from={from} peerId={peerId} />
                ))}
              </ul>
            </div>
            <InputBar />
          </div>
        </div>
      </div>
    </div>
  )
}
