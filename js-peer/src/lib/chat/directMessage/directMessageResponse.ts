import { keys } from '@libp2p/crypto'
import { Connection, Libp2p } from '@libp2p/interface'
import { Uint8ArrayList } from 'uint8arraylist'
import { rpc } from '@/lib/protobuf/directMessage'
import { verifyMessage } from '@/lib/protobuf/helpers/verify'
import { DeepPartial } from '@/types/partial'

// directMessageResponse generates a response to a directMessageRequest to
// indicate that the message was received.
export async function directMessageResponse(
  libp2p: Libp2p,
  status: rpc.Status,
): Promise<Uint8Array> {
  if (!libp2p) {
    throw new Error('no p2p connection')
  }

  if (!libp2p.peerId.privateKey) {
    throw new Error('no local peer private key')
  }

  const privateKey = await keys.unmarshalPrivateKey(libp2p.peerId.privateKey)

  if (!privateKey) {
    throw new Error('unmarshal local peer private key failed')
  }

  let res: DeepPartial<rpc.DirectMessageResponse> = {
    status: status,
    messageData: {
      clientVersion: '0.0.1',
      timestamp: BigInt(Date.now()),
      id: crypto.randomUUID(),
      nodeId: libp2p.peerId.toString(),
      nodePubKey: libp2p.peerId.publicKey,
    },
  }

  const encodedRes = rpc.DirectMessageResponse.encode(
    res as rpc.DirectMessageResponse,
  )

  if (!res.messageData) {
    throw new Error('messageData not set')
  }

  res.messageData.sign = await privateKey.sign(encodedRes)

  const signedEncodedRes = rpc.DirectMessageResponse.encode(
    res as rpc.DirectMessageResponse,
  )

  return signedEncodedRes
}

export async function directMessageRequestProcessChunk(
  chunk: Uint8ArrayList,
  connection: Connection,
): Promise<string> {
  const uint8Array = chunk.subarray()
  const res = rpc.DirectMessageRequest.decode(uint8Array)

  if (!res || !res.messageData) {
    throw new Error('no messageData')
  }

  if (
    !connection ||
    !connection.remotePeer ||
    !connection.remotePeer.publicKey
  ) {
    throw new Error('invalid connection')
  }

  const verifyRes = await verifyMessage(
    res,
    res.messageData.sign,
    connection.remotePeer,
    connection.remotePeer.publicKey,
    rpc.DirectMessageRequest.encode,
  )

  if (!verifyRes) {
    throw new Error('Message verification failed')
  }

  if (!res) {
    throw new Error('no response')
  }

  return res.message
}
