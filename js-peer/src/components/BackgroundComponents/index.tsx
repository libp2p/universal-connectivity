import { AutoDialer } from './AutoDialer'
import { DirectMessageProcessor } from './DirectMessageProcessor'
import { GossipsubProcesser } from './GossipsubProcessor'
import { P2PPinger } from './pinger/P2PPinger'

export const BackgroundComponents = () => {
  return (
    <>
      <AutoDialer />
      <GossipsubProcesser />
      <DirectMessageProcessor />
      <P2PPinger />
    </>
  )
}
