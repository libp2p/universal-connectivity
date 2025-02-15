import { useEffect } from 'react';
import { messageStore } from '@/lib/message-store';
import { useChatContext } from '@/context/chat-ctx';

export const useMessageHistory = (topic: string) => {
  const { setMessageHistory } = useChatContext();

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const messages = await messageStore.getMessagesByTopic(topic);
        if (messages.length > 0) {
          setMessageHistory(messages);
        }
      } catch (error) {
        console.error('Error loading message history:', error);
      }
    };

    loadHistory();
  }, [topic, setMessageHistory]);
};
