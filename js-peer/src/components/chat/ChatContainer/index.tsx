import { ChevronRightIcon } from '@heroicons/react/20/solid'
import { useEffect, useState } from 'react'
import Blockies from 'react-18-blockies'
import { InputBar } from '../InputBar'
import { PeerMessage } from '../PeerMessage'
import { ChatMessage, useChatContext } from '@/context/chat-ctx'
import { shortPeerId } from '@/lib/peers'

export default function ChatContainer() {
  const defaultRoomTitle = 'Public Chat'
  const defaultRoomIcon = '💁🏽‍♀️💁🏿‍♂️'
  const { messageHistory, directMessages, setChatRoom, chatRoom } =
    useChatContext()

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [roomTitle, setRoomTitle] = useState<string>(defaultRoomTitle)
  const [roomIcon, setRoomIcon] = useState<string>(defaultRoomIcon)

  const handleBackToPublicChat = () => {
    setChatRoom('')
    setRoomTitle(defaultRoomTitle)
    setRoomIcon(defaultRoomIcon)
    setMessages(messageHistory)
  }

  useEffect(() => {
    // assumes a chat room is a peerId thus a direct message
    if (chatRoom === '') {
      setRoomTitle(defaultRoomTitle)
      setRoomIcon(defaultRoomIcon)
      setMessages(messageHistory)
    } else {
      setRoomTitle(chatRoom)
      setMessages(directMessages[chatRoom] || [])
      setRoomIcon('')
    }
  }, [chatRoom, directMessages, messageHistory])

  return (
    <div className="h-[calc(100vh-190px)]">
      <div className="container mx-auto">
        <div className="min-w-full border rounded lg:grid lg:grid-cols-3">
          <div className="lg:col-span-3 lg:block">
            <div className="w-full">
              <div className="relative flex items-center p-3 border-b border-gray-300">
                <div className="flex flex-grow">
                  <span className="text-3xl">
                    {roomIcon !== '' ? (
                      roomIcon
                    ) : (
                      <Blockies
                        seed={roomTitle}
                        size={15}
                        scale={3}
                        className="rounded mr-2 max-h-10 max-w-10"
                      />
                    )}
                  </span>
                  <span className="block ml-2 font-bold text-gray-600">
                    {chatRoom ? shortPeerId(roomTitle) : roomTitle}
                  </span>
                </div>
                {chatRoom !== '' && (
                  <button
                    onClick={handleBackToPublicChat}
                    className="text-gray-500 flex sm:hidden"
                  >
                    <span>Back to Public Chat</span>
                    <ChevronRightIcon className="w-6 h-6 text-gray-500" />
                  </button>
                )}
              </div>
              <div className="relative w-full flex flex-col-reverse p-6 h-[calc(100vh-195px)] overflow-y-auto bg-gray-100">
                <ul className="space-y-2">
                  {messages.map(
                    ({
                      msgId,
                      msg,
                      fileObjectUrl,
                      from,
                      peerId,
                      read,
                      receivedAt,
                    }: ChatMessage) => (
                      <PeerMessage
                        key={msgId}
                        dm={chatRoom !== '' ? true : false}
                        msg={msg}
                        fileObjectUrl={fileObjectUrl}
                        from={from}
                        peerId={peerId}
                        read={read}
                        msgId={msgId}
                        receivedAt={receivedAt}
                      />
                    ),
                  )}
                </ul>
              </div>
              <InputBar chatRoom={chatRoom} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
