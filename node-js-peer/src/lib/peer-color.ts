import { PeerId } from '@libp2p/interface'
import { peerIdFromString } from '@libp2p/peer-id'
import { toString as uint8ArrayToString } from 'uint8arrays/to-string'

/**
 * use the last 6 chars of the peer id as a hex code to create a deterministic
 * color
 */
export function peerColor (peerId: PeerId | string): string {
  if (typeof peerId === 'string') {
    peerId = peerIdFromString(peerId)
  }

  const peerIdString = uint8ArrayToString(peerId.toCID().bytes, 'base16')
  return peerIdString.substring(peerIdString.length - 6).toUpperCase()
}
