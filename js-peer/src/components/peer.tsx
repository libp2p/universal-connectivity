import { useLibp2pContext } from "@/context/ctx"
import { Menu, MenuButton, MenuItem, MenuItems, Transition } from "@headlessui/react"
import { Fragment, useEffect, useState } from "react"
import { PeerId } from '@libp2p/interface'
import { useChatContext } from "@/context/chat-ctx"
import Blockies from 'react-18-blockies'
import { classNames } from "@/lib/classes"

interface DMMenuItemProps {
  peerId: PeerId
}

function DMMenuItem({ peerId }: DMMenuItemProps) {
  const { setRoomId } = useChatContext()

  const handleSetRoomId = () => {
    setRoomId(peerId.toString())
  }

  return (
    <MenuItem>
      {({ focus }) => (
        <span
          className={classNames(
            focus ? 'bg-gray-100 text-gray-900' : 'text-gray-700',
            'block px-4 py-2 text-sm',
          )}
          onClick={() => handleSetRoomId()}
        >
          Direct Message
        </span>
      )}
    </MenuItem>
  )
}

interface UnsupportedMenuItemProps {
  text: string
}

function UnsupportedMenuItem({ text }: UnsupportedMenuItemProps) {
  return (
    <MenuItem>
      {({ focus }) => (
        <span
          className={classNames(
            focus ? 'bg-gray-100 text-gray-900' : 'text-gray-700',
            'block px-4 py-2 text-sm',
          )}
        >
          {text}
        </span>
      )}
    </MenuItem>
  )
}

interface UnidentifiedMenuItemProps {
  peerId: PeerId
  state: {
    dialing: boolean
    setDialing: (dialing: boolean) => void
    error: string
    setError: (error: string) => void
  }
}

function UnidentifiedMenuItem({ peerId, state }: UnidentifiedMenuItemProps) {
  const { libp2p } = useLibp2pContext()

  const handleQuery = async () => {
    try {
      state.setError('')
      state.setDialing(true)

      await libp2p.dial(peerId, { signal: AbortSignal.timeout(5000) })
    } catch (e) {
      state.setError(`${e}`)
      console.error('Failed to dial', e)
    } finally {
      state.setDialing(false)
    }
  }

  return (
    <MenuItem>
      {({ focus }) => (
        <span
          className={classNames(
            focus ? 'bg-gray-100 text-gray-900' : 'text-gray-700',
            'block px-4 py-2 text-sm',
          )}
          onClick={() => handleQuery()}
        >
          {!state.dialing && !state.error && 'Dial'}
          {state.dialing && 'Dialing'}
          {!state.dialing && state.error && `Retry (${state.error})`}
        </span>
      )}
    </MenuItem>
  )
}

export interface PeerProps {
  peer: PeerId,
  self: boolean,
  withName: boolean,
  withUnread: boolean
}

export function Peer({ peer, self, withName, withUnread }: PeerProps) {
  const { libp2p } = useLibp2pContext()
  const { directMessages } = useChatContext()
  const [dialing, setDialing] = useState(false)
  const [error, setError] = useState('')
  const [identified, setIdentified] = useState(false)

  useEffect(() => {
    const init = async () => {
      if (await libp2p.peerStore.has(peer)) {
        const p = await libp2p.peerStore.get(peer)
        if (p.protocols.length > 0) {
          setIdentified(true)
        }
      }
    }

    init()
  }, [libp2p.peerStore, peer])

  return (
    <Menu as="div" className="relative inline-block text-left">
      <MenuButton className="inline-flex w-full justify-center rounded-md text-sm font-semibold text-gray-900">
        <Blockies seed={peer.toString()} size={15} scale={3} className="rounded max-h-10 max-w-10" />
        {withName &&
          <div className="w-full">
            <div className="flex justify-between">
              <span className={`block ml-2 font-semibold ${self ? 'text-indigo-700-600' : 'text-gray-600'}`}>
                {peer.toString().slice(-7)}
                {self && ' (You)'}
              </span>
            </div>
            {withUnread && (
              <div className="ml-2 text-gray-600">
                {directMessages[peer.toString()]?.filter((m) => !m.read).length ? `(${directMessages[peer.toString()]?.filter((m) => !m.read).length} unread)` : ''}
              </div>
            )}
          </div>
        }
      </MenuButton>
      {!self &&
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
            <MenuItems className="absolute left-0 z-10 mt-2 w-48 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
              {!identified &&
                <div className="py-1">
                  <UnidentifiedMenuItem
                    peerId={peer}
                    state={{ dialing, setDialing, error, setError }}
                  />
                </div>
              }
              {identified && libp2p.services.directMessage.isDMPeer(peer) &&
                <div className="py-1">
                  <DMMenuItem
                    peerId={peer}
                  />
                </div>
              }
              {identified && !libp2p.services.directMessage.isDMPeer(peer) &&
                <div className="py-1">
                  <UnsupportedMenuItem
                    text="Direct Message Unsupported" />
                </div>
              }
            </MenuItems>
          </Transition>
        </>
      }
    </Menu>
  )
}
