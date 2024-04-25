import { Dialer } from './Dialer'
import { DirectMessageProcessor } from './DirectMessageProcessor'
import { GossipsubChatProcesser } from './GossipsubChatProcessor'
// import { Pinger } from "./Pinger"

export const BackgroundComponents = () => {
  return (
    <>
      <Dialer />
      {/* <Pinger /> */}
      <GossipsubChatProcesser />
      <DirectMessageProcessor />
    </>
  )
}
