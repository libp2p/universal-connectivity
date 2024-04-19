import Attachment from "@/components/icons/Attachment"
import Send from "@/components/icons/Send"
import { ChatMessage, useChatContext } from "@/context/chat-ctx"
import { useLibp2pContext } from "@/context/ctx"
import { ChatFile, useFileChatContext } from "@/context/file-ctx"
import { CHAT_FILE_TOPIC, CHAT_TOPIC } from "@/lib/constants/"
import { useCallback, useRef, useState } from "react"
import { v4 as uuidv4 } from 'uuid';
import { TextInput } from "../TextInput"
import { newChatFileMessage } from "@/lib/chat"

export const InputBar = () => {
  const { libp2p } = useLibp2pContext()
  const { files, setFiles } = useFileChatContext();
  const fileRef = useRef<HTMLInputElement>(null);
  const [input, setInput] = useState<string>('')
  const { messageHistory, setMessageHistory } = useChatContext();

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

  const handleSend = useCallback(
    async (e: React.MouseEvent<HTMLButtonElement>) => {
      sendMessage()
    },
    [sendMessage],
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
    <div className="flex items-center justify-between w-full p-3 border-t border-gray-300">
      {/* <button>
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
              </button> */}

      <input ref={fileRef} className="hidden" type="file" onChange={handleFileInput} />
      <button onClick={handleFileSend}>
        <Attachment />
      </button>
      <TextInput sendMessage={sendMessage} setInput={setInput} input={input} />
      {/* <button>
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
              </button> */}
      <button onClick={handleSend} type="submit">
        <Send />
      </button>
    </div>
  )
}