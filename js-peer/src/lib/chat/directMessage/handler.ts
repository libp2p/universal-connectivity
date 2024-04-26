import { pipe } from 'it-pipe'
import { Libp2p } from 'libp2p'
import {
  directMessageRequestProcessChunk,
  directMessageResponse,
} from './directMessageResponse'
import { toBuffer } from '@/lib/buffer'
import { DIRECT_MESSAGE_PROTOCOL } from '@/lib/constants'
import { rpc } from '@/lib/protobuf/directMessage'

export const directMessageEvent = 'directMessageEvt'

// handleDirectMessageRequest handles inbound direct messages from peers.
// Needs to be registered in libp2p
export async function handleDirectMessageRequest(libp2p: Libp2p) {
  await libp2p.handle(
    DIRECT_MESSAGE_PROTOCOL,
    async ({ stream, connection }) => {
      pipe(
        stream.source, // Source, read data from the stream
        async function (source) {
          let reqData

          for await (const chunk of source) {
            reqData = await directMessageRequestProcessChunk(chunk, connection)
          }

          const eventDetails = {
            request: reqData,
            stream: stream,
            connection: connection,
          }

          document.dispatchEvent(
            new CustomEvent(directMessageEvent, { detail: eventDetails }),
          )
        },
      )

      const signedEncodedRes = await directMessageResponse(
        libp2p,
        rpc.Status.OK,
      )

      await pipe(
        [signedEncodedRes], // array of Uint8Array to send
        toBuffer, // convert strings (or other data) into Buffer before sending
        stream.sink, // Sink, write data to the stream
      )
    },
  )
}
