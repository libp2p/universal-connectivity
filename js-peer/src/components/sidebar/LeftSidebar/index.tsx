import { DirectMessagesList } from '@/components/directmessages/DirectMessagesList'
import { Rooms } from '@/components/Rooms'

export const LeftSidebar = () => {
  return (
    <div className="h-[calc(100vh-65px)] overflow-y-auto px-2 pt-1 bg-gray-200">
      <Rooms />
      <hr className="h-px border-0 my-2 bg-gray-300" />
      <DirectMessagesList />
    </div>
  )
}
