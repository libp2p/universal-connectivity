import { Dialer } from "./Dialer";
import { GossipsubChatProcesser } from "./GossipsubChatProcessor";
// import { Pinger } from "./Pinger"

export const BackgroundComponents = () => {
  return (
    <>
      <Dialer />
      {/* <Pinger /> */}
      <GossipsubChatProcesser />
    </>
  );
};
