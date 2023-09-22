import React, { ReactNode, createContext, useContext, useState } from 'react'
import { Multiaddr } from '@multiformats/multiaddr'

export interface ListenAddresses {
	multiaddrs: Multiaddr[]
}

export interface ListenAddressesContextInterface {
	listenAddresses: ListenAddresses;
	setListenAddresses: (addresses: ListenAddresses) => void;
}

export const listenAddressesContext = createContext<ListenAddressesContextInterface>({
	listenAddresses: {
		multiaddrs: []
	},
	setListenAddresses: () => { }
})

export const useListenAddressesContext = () => {
	return useContext(listenAddressesContext);
};

export const ListenAddressesProvider = ({ children }: { children: ReactNode }) => {
	const [listenAddresses, setListenAddresses] = useState<ListenAddresses>({
		multiaddrs: []
	});

	return (
		<listenAddressesContext.Provider value={{ listenAddresses, setListenAddresses }}>
			{children}
		</listenAddressesContext.Provider>
	);
};
