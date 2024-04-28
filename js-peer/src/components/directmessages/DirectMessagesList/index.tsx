import ChatBubbleLeftRightIcon from '@heroicons/react/24/outline/ChatBubbleLeftRightIcon'
import { useRouter } from 'next/router'
import { Peer } from './Peer'
import { useChatContext } from '@/context/chat-ctx'

interface Props {
  isMobilePage?: boolean
}
export const DirectMessagesList = ({ isMobilePage = false }: Props) => {
  const router = useRouter()
  const { setChatRoom, directMessages } = useChatContext()

  const handleChangeChatRoom = (peerId: string) => {
    setChatRoom(peerId)
    if (isMobilePage) {
      router.push('/chat')
    }
  }

  return (
    <div>
      <div
        className={
          isMobilePage
            ? 'flex relative items-center p-4 border-b border-gray-300'
            : 'flex'
        }
      >
        <ChatBubbleLeftRightIcon className="w-6 h-6 text-gray-400 mr-1" />
        <h3 className="font-bold text-gray-600">Direct Messages</h3>
      </div>
      <div
        className={
          isMobilePage
            ? 'bg-gray-100 h-[calc(100vh-120px)] overflow-y-auto'
            : ''
        }
      >
        {Object.keys(directMessages).map((peerId) => {
          return (
            <div
              key={peerId}
              onClick={() => handleChangeChatRoom(peerId)}
              className={
                isMobilePage ? 'cursor-pointer px-4 py-2' : 'cursor-pointer p-1'
              }
            >
              <Peer peerId={peerId} />
            </div>
          )
        })}
      </div>
    </div>
  )
}
