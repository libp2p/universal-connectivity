import { Menu, Transition } from '@headlessui/react'
import { Fragment } from 'react'
import Blockies from 'react-18-blockies'
import { useChatContext } from '@/context/chat-ctx'
import { shortPeerId } from '@/lib/peers'

export interface Props {
  peerId: string
  me?: boolean
}

function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(' ')
}

export default function Peer({ peerId, me }: Props) {
  const { setChatRoom } = useChatContext()

  const handleSetChatRoom = () => {
    setChatRoom(peerId)
  }

  return (
    <Menu as="div" className="relative inline-block text-left">
      <div>
        <Menu.Button className="inline-flex w-full justify-center rounded-md text-sm font-semibold text-gray-900 hover:bg-gray-50">
          <Blockies
            seed={peerId}
            size={15}
            scale={3}
            className="rounded-full mr-2 max-h-10 max-w-10"
          />
          {shortPeerId(peerId)} {me && <>(Me)</>}
        </Menu.Button>
      </div>

      {!me && (
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
                      onClick={() => handleSetChatRoom()}
                    >
                      Message
                    </span>
                  )}
                </Menu.Item>
                {/*<Menu.Item>
                {({ active }) => (
                  <a
                    href="#"
                    className={classNames(
                      active ? 'bg-gray-100 text-gray-900' : 'text-gray-700',
                      'block px-4 py-2 text-sm'
                    )}
                  >
                    Call
                  </a>
                )}
              </Menu.Item>*/}
              </div>
            </Menu.Items>
          </Transition>
        </>
      )}
    </Menu>
  )
}
