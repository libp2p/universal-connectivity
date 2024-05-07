import React, { ReactNode, createContext, useContext, useState } from 'react';
import type { Connection } from '@libp2p/interface'
import { PeerId } from '@libp2p/interface'


export interface PeerStats {
	peerIds: PeerId[]
	connections: Connection[]
	latency: number
}

export interface PeerContextInterface {
	peerStats: PeerStats;
	setPeerStats: (peerStats: PeerStats) => void;
}
export const peerContext = createContext<PeerContextInterface>({
	peerStats: {
		peerIds: [],
		connections: [],
		latency: 0
	},
	setPeerStats: () => { }
})

export const usePeerContext = () => {
	return useContext(peerContext);
};

export const PeerProvider = ({ children }: { children: ReactNode }) => {
	const [peerStats, setPeerStats] = useState<PeerStats>({
		peerIds: [],
		connections: [],
		latency: 0
	});

	return (
		<peerContext.Provider value={{ peerStats, setPeerStats }}>
			{children}
		</peerContext.Provider>
	);
};

