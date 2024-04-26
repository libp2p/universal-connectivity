import { AutoDialer } from './AutoDialer'
import { DirectMessageProcessor } from './DirectMessageProcessor'
import { GossipsubChatProcesser } from './GossipsubChatProcessor'
// import { Pinger } from "./Pinger"

export const BackgroundComponents = () => {
  return (
    <>
      {/* <Pinger /> */}
      <AutoDialer />
      <GossipsubChatProcesser />
      <DirectMessageProcessor />
    </>
  )
}
