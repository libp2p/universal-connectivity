import { PeerId, isPeerId } from '@libp2p/interface'

/**
 * Returns the last `length` characters of the peer id
 */
export function shortPeerId (peerId: PeerId | string, length = 7): string {
  if (isPeerId(peerId)) {
    peerId = peerId.toString()
  }

  return peerId.substring(peerId.length - length)
}
