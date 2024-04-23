import { GossipsubChatProcesser } from "./GossipsubChatProcessor"
import { Dialer } from "./Dialer"
// import { Pinger } from "./Pinger"

export const BackgroundComponents = () => {
  return (
    <>
      <Dialer />
      {/* <Pinger /> */}
      <GossipsubChatProcesser />
    </>
  )
}
