import { keys } from '@libp2p/crypto'
import { PeerId } from '@libp2p/interface'
import { createFromPubKey } from '@libp2p/peer-id-factory'
import { rpc } from '../directMessage'

async function verifySignature(
  publickKey: Uint8Array,
  msg: rpc.DirectMessageRequest | rpc.DirectMessageResponse,
  signature: Uint8Array,
  encodeFunc: (
    obj: Partial<rpc.DirectMessageRequest | rpc.DirectMessageResponse>,
  ) => Uint8Array,
): Promise<boolean> {
  if (!msg.messageData) {
    throw new Error('auth no messageData')
  }

  msg.messageData.sign = new Uint8Array()
  const data = encodeFunc(msg)

  return await keys.unmarshalPublicKey(publickKey).verify(data, signature)
}

export async function verifyMessage(
  msg: rpc.DirectMessageRequest | rpc.DirectMessageResponse,
  signature: Uint8Array,
  peerId: PeerId,
  pubKeyData: Uint8Array,
  encodeFunc: (
    obj: Partial<rpc.DirectMessageRequest | rpc.DirectMessageResponse>,
  ) => Uint8Array,
): Promise<boolean> {
  if (!msg.messageData) {
    throw new Error('auth no messageData')
  }

  if (!pubKeyData) {
    throw new Error('no pubKeyData')
  }

  const key = keys.unmarshalPublicKey(pubKeyData)
  const idFromKey = await createFromPubKey(key)

  if (!idFromKey.equals(peerId)) {
    throw new Error('peer id does not match idFromKey')
  }

  if (!verifySignature(pubKeyData, msg, signature, encodeFunc)) {
    throw new Error('verifySignature failed')
  }

  return true
}
