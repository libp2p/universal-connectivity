import { ConnectedPeerList } from '@/components/PeerList'
import { RecentlySeen } from '@/components/RecentlySeen'

export const RightSidebar = () => {
  return (
    <div className="h-[calc(100vh-65px)] overflow-y-auto px-2 pt-1 bg-gray-200">
      <RecentlySeen />
      <hr className="h-px border-0 my-2 bg-gray-300" />
      <ConnectedPeerList showShortPeerId />
    </div>
  )
}
