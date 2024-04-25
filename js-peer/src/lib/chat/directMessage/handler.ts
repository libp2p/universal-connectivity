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

// handleDirectMessageRequest handles inbound direct messages from peers
// Needs to be registered in libp2p
export async function handleDirectMessageRequest(libp2p: Libp2p) {
  await libp2p.handle(
    DIRECT_MESSAGE_PROTOCOL,
    async ({ stream, connection }) => {
      // eslint-disable-next-line no-console
      console.log(`${DIRECT_MESSAGE_PROTOCOL} got request`)

      pipe(
        stream.source, // Source, read data from the stream
        async function(source) {
          let reqData

          for await (const chunk of source) {
            reqData = await directMessageRequestProcessChunk(chunk, connection)
          }

          // eslint-disable-next-line no-console
          console.log(`${DIRECT_MESSAGE_PROTOCOL} processed chunk: `, reqData)

          // eslint-disable-next-line no-console
          console.log(`dispatching ${directMessageEvent}`)

          const eventDetails = {
            request: reqData,
            stream: stream,
            connection: connection,
          }

          const dres = document.dispatchEvent(
            new CustomEvent(directMessageEvent, { detail: eventDetails }),
          )

          console.log(`dispatched ${directMessageEvent} res: ${dres}`)
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
