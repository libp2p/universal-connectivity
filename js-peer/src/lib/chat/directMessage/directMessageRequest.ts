import { keys } from '@libp2p/crypto'
import { Connection, Libp2p, PeerId, Stream } from '@libp2p/interface'
import { peerIdFromString } from '@libp2p/peer-id'
import { Multiaddr } from '@multiformats/multiaddr'
import { pipe } from 'it-pipe'
import { Uint8ArrayList } from 'uint8arraylist'
import { toBuffer } from '@/lib/buffer'
import { DIRECT_MESSAGE_PROTOCOL } from '@/lib/constants'
import { rpc } from '@/lib/protobuf/directMessage'
import { verifyMessage } from '@/lib/protobuf/helpers/verify'
import { DeepPartial } from '@/types/partial'

interface Params {
  libp2p: Libp2p
  peerId: PeerId | Multiaddr | string
  message: string
}

// Send direct message to peer
export const directMessageRequest = async ({
  libp2p,
  peerId,
  message,
}: Params): Promise<boolean> => {
  const protocol = DIRECT_MESSAGE_PROTOCOL

  if (!libp2p) {
    throw new Error('no libp2p')
  }

  if (!libp2p.peerId.privateKey) {
    throw new Error('no local peer private key')
  }

  if (!libp2p.peerId.publicKey) {
    throw new Error('no public key')
  }

  if (!peerId) {
    throw new Error('no recipent peerId set')
  }

  if (!message) {
    throw new Error('empty message')
  }

  if (typeof peerId === 'string') {
    peerId = peerIdFromString(peerId)
  }

  const privateKey = await keys.unmarshalPrivateKey(libp2p.peerId.privateKey)

  if (!privateKey) {
    throw new Error('unmarshal local peer private key failed')
  }

  let req: DeepPartial<rpc.DirectMessageRequest> = {
    message: message,
    messageData: {
      clientVersion: '0.0.1',
      timestamp: BigInt(Date.now()),
      id: crypto.randomUUID(),
      nodeId: libp2p.peerId.toString(),
      nodePubKey: libp2p.peerId.publicKey,
    },
  }

  const encodedReq = rpc.DirectMessageRequest.encode(
    req as rpc.DirectMessageRequest,
  )

  if (!req.messageData) {
    throw new Error('messageData not set')
  }

  req.messageData.sign = await privateKey.sign(encodedReq)

  const signedEncodedReq = rpc.DirectMessageRequest.encode(
    req as rpc.DirectMessageRequest,
  )

  let stream: Stream | undefined

  let response = false

  // TODO timeout
  try {
    const conn = await libp2p.dial(peerId)

    console.log('connection: ', conn)

    const p = await libp2p.peerStore.get(peerId as PeerId)

    console.log('p: ', p.protocols)

    stream = await conn.newStream([protocol])

    await pipe(
      [signedEncodedReq], // array of Uint8Array to send
      toBuffer, // convert strings (or other data) into Buffer before sending
      stream.sink, // Sink, write data to the stream
    )

    await pipe(
      stream.source, // Source, read data from the stream
      async function(source) {
        for await (const chunk of source) {
          response = await directMessageResponseProcessChunk(chunk, conn)
        }
      },
    )
  } catch (e: any) {
    if (stream) {
      stream.abort(e)
    }

    throw e
  } finally {
    if (stream) {
      await stream.close()
    }
  }

  if (!response) {
    throw new Error('response was not true')
  }

  // eslint-disable-next-line no-console
  console.log('response was true, peer received message', response)

  if (stream) {
    await stream.close()
  }

  return true
}

async function directMessageResponseProcessChunk(
  chunk: Uint8ArrayList,
  connection: Connection,
): Promise<boolean> {
  const uint8Array = chunk.subarray()
  const res = rpc.DirectMessageResponse.decode(uint8Array)

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
    rpc.DirectMessageResponse.encode,
  )

  if (!verifyRes) {
    throw new Error('Message verification failed')
  }

  if (!res) {
    throw new Error('no response')
  }

  if (res.status !== rpc.Status.OK) {
    // eslint-disable-next-line no-console
    console.log(res.statusText)
    throw new Error('status: not OK')
  }

  return true
}
