import React, { useCallback, useRef, useState } from 'react'
import { toast } from 'react-toastify'
import { v4 as uuidv4 } from 'uuid'
import { TextInput } from '../TextInput'
import Attachment from '@/components/icons/Attachment'
import Send from '@/components/icons/Send'
import Spinner from '@/components/icons/Spinner'
import { ChatMessage, useChatContext } from '@/context/chat-ctx'
import { useLibp2pContext } from '@/context/ctx'
import { ChatFile, useFileChatContext } from '@/context/file-ctx'
import { newChatFileMessage } from '@/lib/chat'
import { directMessageRequest } from '@/lib/chat/directMessage/directMessageRequest'
import { CHAT_FILE_TOPIC, CHAT_TOPIC } from '@/lib/constants/'

interface Props {
  chatRoom: string
}

export const InputBar = ({ chatRoom }: Props) => {
  const { libp2p } = useLibp2pContext()
  const { files, setFiles } = useFileChatContext()
  const fileRef = useRef<HTMLInputElement>(null)
  const [input, setInput] = useState<string>('')
  const [isSending, setIsSending] = useState<boolean>(false)

  const {
    directMessages,
    setDirectMessages,
    messageHistory,
    setMessageHistory,
  } = useChatContext()

  const sendGossipsubMessage = useCallback(async () => {
    try {
      setIsSending(true)
      console.log(
        `peers in gossip for topic ${CHAT_TOPIC}:`,
        libp2p.services.pubsub.getSubscribers(CHAT_TOPIC).toString(),
      )

      const res = await libp2p.services.pubsub.publish(
        CHAT_TOPIC,
        new TextEncoder().encode(input),
      )

      console.log(
        'sent message via gossipsub: ',
        res.recipients.map((peerId) => peerId.toString()),
      )

      const myPeerId = libp2p.peerId.toString()

      setMessageHistory([
        ...messageHistory,
        {
          msgId: crypto.randomUUID(),
          msg: input,
          fileObjectUrl: undefined,
          from: 'me',
          peerId: myPeerId,
          read: true,
          receivedAt: Date.now(),
        },
      ])
      setInput('')
    } catch (e: any) {
      toast.error(`Failed to send: ${e.message}`)
      console.error(e)
    } finally {
      setIsSending(false)
    }
  }, [input, messageHistory, setInput, libp2p, setMessageHistory])

  const sendDM = useCallback(async () => {
    try {
      setIsSending(true)
      const res = await directMessageRequest({
        libp2p,
        peer: chatRoom,
        message: input,
      })

      if (!res) {
        toast('Failed to send message')
        return
      }

      const myPeerId = libp2p.peerId.toString()

      const newMessage: ChatMessage = {
        msgId: crypto.randomUUID(),
        msg: input,
        fileObjectUrl: undefined,
        from: 'me',
        peerId: myPeerId,
        read: true,
        receivedAt: Date.now(),
      }

      const updatedMessages = directMessages[chatRoom]
        ? [...directMessages[chatRoom], newMessage]
        : [newMessage]

      setDirectMessages({
        ...directMessages,
        [chatRoom]: updatedMessages,
      })

      setInput('')
    } catch (e: any) {
      toast.error(`Failed to send: ${e.message}`)
      console.error(e)
    } finally {
      setIsSending(false)
    }
  }, [libp2p, setDirectMessages, directMessages, chatRoom, input])

  const sendMessage = useCallback(async () => {
    if (input === '') {
      return
    }

    if (chatRoom != '') {
      sendDM()
      // send DM message
    } else {
      // send Gossipsub message to public chat
      sendGossipsubMessage()
    }
  }, [chatRoom, input, sendDM, sendGossipsubMessage])

  const sendFile = useCallback(
    async (readerEvent: ProgressEvent<FileReader>) => {
      const fileBody = readerEvent.target?.result as ArrayBuffer

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
        new TextEncoder().encode(file.id),
      )

      console.log(
        'sent file to: ',
        res.recipients.map((peerId) => peerId.toString()),
      )

      const msg: ChatMessage = {
        msgId: crypto.randomUUID(),
        msg: newChatFileMessage(file.id, file.body),
        fileObjectUrl: window.URL.createObjectURL(new Blob([file.body])),
        from: 'me',
        peerId: myPeerId,
        read: true,
        receivedAt: Date.now(),
      }

      setMessageHistory([...messageHistory, msg])
    },
    [messageHistory, libp2p, setMessageHistory, files, setFiles],
  )

  const handleSend = useCallback(async () => {
    sendMessage()
  }, [sendMessage])

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        const reader = new FileReader()

        reader.readAsArrayBuffer(e.target.files[0])
        reader.onload = (readerEvent) => {
          sendFile(readerEvent)
        }
      }
    },
    [sendFile],
  )

  const handleFileSend = useCallback(async () => {
    fileRef?.current?.click()
  }, [fileRef])

  return (
    <div className="flex items-center justify-between w-full p-3 border-t border-gray-300">
      <input
        ref={fileRef}
        className="hidden"
        type="file"
        onChange={handleFileInput}
      />
      <button onClick={handleFileSend}>
        <Attachment />
      </button>
      <TextInput
        sendMessage={sendMessage}
        setInput={setInput}
        input={input}
        isDisabled={isSending}
      />
      {isSending ? (
        <Spinner />
      ) : (
        <button onClick={handleSend} type="submit">
          <Send />
        </button>
      )}
    </div>
  )
}
