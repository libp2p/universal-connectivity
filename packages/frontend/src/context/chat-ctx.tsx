import React, { createContext, useContext, useState } from 'react';

export interface ChatMessage {
	msg: string
	fileObjectUrl: string | undefined
	from: 'me' | 'other'
	peerId: string
}

export interface ChatContextInterface {
	messageHistory: ChatMessage[];
	setMessageHistory: (messageHistory: ChatMessage[]) => void;
}
export const chatContext = createContext<ChatContextInterface>({
	messageHistory: [],
	setMessageHistory: () => { }
})

export const useChatContext = () => {
	return useContext(chatContext);
};

export const ChatProvider = ({ children }: any) => {
	const [messageHistory, setMessageHistory] = useState<ChatMessage[]>([]);

	return (
		<chatContext.Provider value={{ messageHistory, setMessageHistory }}>
			{children}
		</chatContext.Provider>
	);
};

