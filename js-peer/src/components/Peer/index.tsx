import { Menu, Transition } from '@headlessui/react'
import { peerIdFromString } from '@libp2p/peer-id'
import { Fragment, useEffect, useState } from 'react'
import Blockies from 'react-18-blockies'
import { useChatContext } from '@/context/chat-ctx'
import { useLibp2pContext } from '@/context/ctx'
import { shortPeerId } from '@/lib/peers'

export interface Props {
  peerId: string
  me?: boolean
}

function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(' ')
}

interface MenuItemProps {
  protocol: string
  peerId: string
}
export const MenuItem = ({ protocol, peerId }: MenuItemProps) => {
  const { setChatRoom } = useChatContext()

  const handleSetChatRoom = () => {
    setChatRoom(peerId)
  }

  if (protocol === '/universal-connectivity/dm/1.0.0') {
    return (
      <Menu.Item>
        {({ active }) => (
          <span
            className={classNames(
              active ? 'bg-gray-100 text-gray-900' : 'text-gray-700',
              'block px-4 py-2 text-sm',
            )}
            onClick={() => handleSetChatRoom()}
          >
            Message
          </span>
        )}
      </Menu.Item>
    )
  }
}

export default function Peer({ peerId, me }: Props) {
  const { libp2p } = useLibp2pContext()
  const [commsProtocols, setCommsProtocols] = useState<string[]>([])

  useEffect(() => {
    const init = async () => {
      if (await libp2p.peerStore.has(peerIdFromString(peerId))) {
        const peer = await libp2p.peerStore.get(peerIdFromString(peerId))

        setCommsProtocols(
          peer.protocols.filter(
            (p) =>
              p.startsWith('/universal-connectivity/') &&
              p !== '/universal-connectivity/kad/1.0.0' &&
              p !== '/universal-connectivity/lan/kad/1.0.0',
          ),
        )
        // console.log("protos", peerId, commsProtocols)
      }
    }

    init()
  }, [libp2p.peerStore, peerId])

  return (
    <Menu as="div" className="relative inline-block text-left">
      <div>
        <Menu.Button className="inline-flex w-full justify-center rounded-md text-sm font-semibold text-gray-900">
          <Blockies
            seed={peerId}
            size={15}
            scale={3}
            className="rounded mr-2 max-h-10 max-w-10"
          />
          {shortPeerId(peerId)} {me && <>(Me)</>}
        </Menu.Button>
      </div>

      {!me && commsProtocols.length > 0 && (
        <>
          <Transition
            as={Fragment}
            enter="transition ease-out duration-100"
            enterFrom="transform opacity-0 scale-95"
            enterTo="transform opacity-100 scale-100"
            leave="transition ease-in duration-75"
            leaveFrom="transform opacity-100 scale-100"
            leaveTo="transform opacity-0 scale-95"
          >
            <Menu.Items className="absolute left-0 z-10 mt-2 w-48 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
              <div className="py-1">
                {commsProtocols.map((protocol) => {
                  return (
                    <MenuItem
                      key={protocol}
                      protocol={protocol}
                      peerId={peerId}
                    />
                  )
                })}
              </div>
            </Menu.Items>
          </Transition>
        </>
      )}
      {!me && commsProtocols.length === 0 && (
        <>
          <Transition
            as={Fragment}
            enter="transition ease-out duration-100"
            enterFrom="transform opacity-0 scale-95"
            enterTo="transform opacity-100 scale-100"
            leave="transition ease-in duration-75"
            leaveFrom="transform opacity-100 scale-100"
            leaveTo="transform opacity-0 scale-95"
          >
            <Menu.Items className="absolute left-0 z-10 mt-2 w-48 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
              <div className="py-1">
                <Menu.Item>
                  {({ active }) => (
                    <span
                      className={classNames(
                        active ? 'bg-gray-100 text-gray-900' : 'text-gray-700',
                        'block px-4 py-2 text-sm',
                      )}
                    >
                      No protocols identified
                    </span>
                  )}
                </Menu.Item>
              </div>
            </Menu.Items>
          </Transition>
        </>
      )}
    </Menu>
  )
}
