import { PeerMessage } from '../PeerMessage'
import { InputBar } from '../InputBar'
import { ChatMessage, useChatContext } from '@/context/chat-ctx';
import { useEffect, useState } from 'react';
import Blockies from 'react-18-blockies'

export default function ChatContainer() {
  const defaultRoomTitle = 'Public Chat'
  const defaultRoomIcon = '💁🏽‍♀️💁🏿‍♂️'
  const { messageHistory, dmMessages, chatRoom } = useChatContext()

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [roomTitle, setRoomTitle] = useState<string>(defaultRoomTitle)
  const [roomIcon, setRoomIcon] = useState<string>(defaultRoomTitle)


  useEffect(() => {
    if (chatRoom === '') {
      setRoomTitle(defaultRoomTitle)
      setRoomIcon(defaultRoomIcon)
      setMessages(messageHistory)
    } else {
      setRoomTitle(chatRoom);
      setMessages(dmMessages[chatRoom] || [])
      setRoomIcon('')
    }
  }, [chatRoom, dmMessages, messageHistory]);

  return (
    <div className="max-h-screen">
      <div className="container mx-auto">
        <div className="min-w-full border rounded lg:grid lg:grid-cols-3">
          <div className="lg:col-span-3 lg:block">
            <div className="w-full">
              <div className="relative flex items-center p-3 border-b border-gray-300">
                <span className="text-3xl">{roomIcon !== '' ? roomIcon : <Blockies seed={roomTitle} size={15} scale={3} className="rounded mr-2 max-h-10 max-w-10" />}</span>
                <span className="block ml-2 font-bold text-gray-600">
                  {roomTitle}
                </span>
              </div>
              <div className="relative w-full flex flex-col-reverse p-6 overflow-y-auto h-[40rem] bg-gray-100">
                <ul className="space-y-2">
                  {messages.map(({ msgId, msg, fileObjectUrl, from, peerId, read }: ChatMessage) => (
                    <PeerMessage key={msgId} dm={false} msg={msg} fileObjectUrl={fileObjectUrl} from={from} peerId={peerId} read={read} msgId={msgId} />
                  ))}
                </ul>
              </div>
              <InputBar />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
