import { Libp2p, PeerId, Stream, Connection } from '@libp2p/interface'
import { DIRECT_MESSAGE_PROTOCOL } from '@/lib/constants'
import { dm } from '@/lib/protobuf/direct-message'
import { pbStream } from 'it-protobuf-stream'

export const directMessageEvent = 'directMessageEvt'

export interface DirectMessageEvent {
  content: string
  type: string
  stream: Stream
  connection: Connection
}

export const dmClientVersion = '0.0.1'

export const mimeTextPlain = 'text/plain'

interface Props {
  libp2p: Libp2p
  peerId: PeerId
  message: string
}

export const handleSendDirectMessage = async ({
  libp2p,
  peerId,
  message,
}: Props): Promise<boolean> => {
  if (!message) {
    throw new Error('empty message')
  }

  let stream: Stream | undefined

  try {
    const stream = await libp2p.dialProtocol(peerId, DIRECT_MESSAGE_PROTOCOL, { signal: AbortSignal.timeout(5000) })

    if (!stream) {
      throw new Error('no stream')
    }

    const datastream = pbStream(stream)

    const req: dm.DirectMessageRequest = {
      content: message,
      type: mimeTextPlain,
      metadata: {
        clientVersion: dmClientVersion,
        timestamp: BigInt(Date.now()),
      },
    }

    await datastream.write(req, dm.DirectMessageRequest)

    const res = await datastream.read(dm.DirectMessageResponse)

    if (!res) {
      throw new Error('no response')
    }

    if (!res.metadata) {
      throw new Error('no meta')
    }

    if (res.status !== dm.Status.OK) {
      throw new Error(`status: not OK, received: ${res.status}`)
    }
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

  return true
}

export const handleInboundDirectMessage = async (stream: Stream, connection: Connection) => {
  const datastream = pbStream(stream)

  const req = await datastream.read(dm.DirectMessageRequest)

  const res: dm.DirectMessageResponse = {
    status: dm.Status.OK,
    metadata: {
      clientVersion: dmClientVersion,
      timestamp: BigInt(Date.now()),
    },
  }

  await datastream.write(res, dm.DirectMessageResponse)

  const detail = {
    content: req.content,
    type: req.type,
    stream: stream,
    connection: connection
  } as DirectMessageEvent

  document.dispatchEvent(
    new CustomEvent(directMessageEvent, { detail })
  )
}
