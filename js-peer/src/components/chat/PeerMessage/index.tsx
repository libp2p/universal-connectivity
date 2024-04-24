import React, { useEffect } from "react";
import Peer from "@/components/Peer";
import { ChatMessage, useChatContext } from "@/context/chat-ctx";

interface Props extends ChatMessage {
  dm: boolean;
}

export const PeerMessage = ({
  msgId,
  msg,
  fileObjectUrl,
  from,
  peerId,
  read,
  dm,
}: Props) => {
  const { messageHistory, setMessageHistory, dmMessages, setDMMessages } =
    useChatContext();

  useEffect(() => {
    if (read) {
      return;
    }

    if (dm) {
      setDMMessages({
        ...dmMessages,
        [peerId]: dmMessages[peerId].map((m) => {
          if (m.msgId === msgId) {
            return { ...m, read: true };
          }

          return m;
        }),
      });
    } else {
      for (const message of messageHistory) {
        if (message.msgId === msgId) {
          setMessageHistory(
            messageHistory.map((m) => {
              if (m.msgId === msgId) {
                return { ...m, read: true };
              }

              return m;
            })
          );
        }
      }
    }
  }, [
    dm,
    dmMessages,
    messageHistory,
    msgId,
    peerId,
    read,
    setDMMessages,
    setMessageHistory,
  ]);

  return (
    <li>
      <Peer peerId={peerId} me={from === "me"} />
      <div className="relative -top-6 left-11 w-[calc(100%-2.5rem)] px-4 py-2 text-gray-700 rounded shadow bg-white">
        <div className="block">
          {msg}
          <p>
            {fileObjectUrl ? (
              <a href={fileObjectUrl} target="_blank" rel="noreferrer">
                <b>Download</b>
              </a>
            ) : (
              ""
            )}
          </p>
        </div>
      </div>
    </li>
  );
};
