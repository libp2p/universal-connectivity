import { ConnectedPeerList } from '@/components/PeerList'
import { RecentlySeen } from '@/components/RecentlySeen'

export const RightSidebar = () => {
  return (
    <>
      <RecentlySeen />
      <ConnectedPeerList showShortPeerId />
    </>
  )
}
