import React, { createContext, useContext, useEffect, useState } from 'react';
import { useLibp2pContext } from './ctx';
import type { Message } from '@libp2p/interface'
import { CHAT_FILE_TOPIC, CHAT_TOPIC, FILE_EXCHANGE_PROTOCOL, PUBSUB_PEER_DISCOVERY } from '@/lib/constants'
import { toString as uint8ArrayToString } from 'uint8arrays/to-string'
import { fromString as uint8ArrayFromString } from 'uint8arrays/from-string'
import { pipe } from 'it-pipe'
import map from 'it-map'
import * as lp from 'it-length-prefixed'


export interface ChatMessage {
	msg: string
	fileObjectUrl: string | undefined
	from: 'me' | 'other'
	peerId: string
}

export interface ChatFile {
  id: string
  body: Uint8Array
  sender: string
}

export interface ChatContextInterface {
	messageHistory: ChatMessage[];
	setMessageHistory: (messageHistory: ChatMessage[]) => void;
  files: Map<string, ChatFile>
  setFiles: (files: Map<string, ChatFile>) => void;
}
export const chatContext = createContext<ChatContextInterface>({
	messageHistory: [],
  files: new Map<string, ChatFile>(),
	setMessageHistory: () => { },
  setFiles: () => { }
})

export const useChatContext = () => {
	return useContext(chatContext);
};

export const ChatProvider = ({ children }: any) => {
	const [messageHistory, setMessageHistory] = useState<ChatMessage[]>([]);
  const [files, setFiles] = useState<Map<string, ChatFile>>(new Map<string, ChatFile>());
  const { libp2p } = useLibp2pContext()

  const messageCB = (evt: CustomEvent<Message>) => {
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
      case PUBSUB_PEER_DISCOVERY: {
        peerDiscoveryCB(evt, topic, data)
        break
      }
      default: {
        throw new Error(`Unexpected gossipsub topic: ${topic}`)
      }
    }
  }

  const chatMessageCB = (evt: CustomEvent<Message>, topic: string, data: Uint8Array) => {
    const msg = new TextDecoder().decode(data)
    console.log(`${topic}: ${msg}`)

    // Append signed messages, otherwise discard
    if (evt.detail.type === 'signed') {
      setMessageHistory([...messageHistory, { msg, fileObjectUrl: undefined, from: 'other', peerId: evt.detail.from.toString() }])
    }
  }

  const peerDiscoveryCB = (evt: CustomEvent<Message>, topic: string, data: Uint8Array) => {
    // TODO: handle peer discovery events
  }

  const chatFileMessageCB = async (evt: CustomEvent<Message>, topic: string, data: Uint8Array) => {
    const newChatFileMessage = (id: string, body: Uint8Array) => {
      return `File: ${id} (${body.length} bytes)`
    }
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

  useEffect(() => {
    libp2p.services.pubsub.addEventListener('message', messageCB)

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
        libp2p.services.pubsub.removeEventListener('message', messageCB)
        await libp2p.unhandle(FILE_EXCHANGE_PROTOCOL)
      })();
    }
  })


	return (
		<chatContext.Provider value={{ messageHistory, setMessageHistory, files, setFiles }}>
			{children}
		</chatContext.Provider>
	);
};

