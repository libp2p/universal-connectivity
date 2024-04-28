import { Peer } from './Peer'
import { useChatContext } from '@/context/chat-ctx'

export const DirectMessagesList = () => {
  const { setChatRoom, directMessages } = useChatContext()

  const handleChangeChatRoom = (peerId: string) => {
    setChatRoom(peerId)
  }

  return (
    <div>
      <h3 className="font-bold text-gray-600">Direct Messages</h3>
      {Object.keys(directMessages).map((peerId) => {
        return (
          <div
            key={peerId}
            onClick={() => handleChangeChatRoom(peerId)}
            className="cursor-pointer p-1"
          >
            <Peer peerId={peerId} />
          </div>
        )
      })}
    </div>
  )
}
