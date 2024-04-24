import { useEffect } from "react";
import { useLibp2pContext } from "@/context/ctx";
import { CHAT_TOPIC } from "@/lib/constants/";

export const Dialer = () => {
  const { libp2p } = useLibp2pContext();

  // Gossipsub pubsub
  useEffect(() => {
    if (!libp2p) {
      return;
    }

    const pubsubMsg = async (evt: CustomEvent<any>) => {
      if (!evt || !evt.detail || !evt.detail.from || !evt.detail.topic) {
        // eslint-disable-next-line no-console
        console.warn("invalid pubsub message", evt);
        return;
      }

      if (evt.detail.topic !== CHAT_TOPIC) {
        // eslint-disable-next-line no-console
        console.debug(
          `skipping non-${CHAT_TOPIC} pubsub messages (${evt.detail.topic}, ${evt.detail.from}, ${evt}`
        );
        return;
      }

      // eslint-disable-next-line no-console
      console.log(`received ${CHAT_TOPIC} pubsub message`, evt.detail);

      try {
        if (!(await libp2p.peerStore.has(evt.detail.from))) {
          // eslint-disable-next-line no-console
          console.log("undiscovered peer", evt.detail.from.toString());

          await libp2p.dial(evt.detail.from);
        }
      } catch (e: any) {
        // eslint-disable-next-line no-console
        console.log("error", e);
      }
    };

    // libp2p.services.pubsub.subscribe(CHAT_TOPIC)
    libp2p.services.pubsub.addEventListener("message", pubsubMsg);

    return () => {
      if (libp2p && libp2p.services && libp2p.services.pubsub) {
        // console.log('unsubscribing from pubsub')
        // libp2p.services.pubsub.unsubscribe(CHAT_TOPIC)

        console.log("removing pubsub event listener");
        libp2p.services.pubsub.removeEventListener("message", pubsubMsg);
      }
    };
  }, [libp2p]);

  return <></>;
};
