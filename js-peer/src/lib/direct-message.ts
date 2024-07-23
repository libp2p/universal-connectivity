import { PeerId, Stream, Connection, CustomEvent, TypedEventEmitter, Startable } from '@libp2p/interface'
import { DIRECT_MESSAGE_PROTOCOL, MIME_TEXT_PLAIN } from '@/lib/constants'
import { serviceCapabilities, serviceDependencies } from '@libp2p/interface'
import type { ConnectionManager } from '@libp2p/interface-internal'
import type { Registrar } from '@libp2p/interface-internal'
import { dm } from '@/lib/protobuf/direct-message'
import { pbStream } from 'it-protobuf-stream'

export const dmClientVersion = '0.0.1'
export const directMessageEvent = 'message'

const ERRORS = {
  EMPTY_MESSAGE: 'Message cannot be empty',
  NO_CONNECTION: 'Failed to create connection',
  NO_STREAM: 'Failed to create stream',
  NO_RESPONSE: 'No response received',
  NO_METADATA: 'No metadata in response',
  STATUS_NOT_OK: (status: dm.Status) => `Received status: ${status}, expected OK`
}

export interface DirectMessageEvent {
  content: string
  type: string
  stream: Stream
  connection: Connection
}

export interface DirectMessageEvents {
  'message': CustomEvent<DirectMessageEvent>
}

interface DirectMessageComponents {
  registrar: Registrar
  connectionManager: ConnectionManager
}

export class DirectMessage extends TypedEventEmitter<DirectMessageEvents> implements Startable {
  readonly [serviceDependencies]: string[] = [
    '@libp2p/identify',
    '@libp2p/connection-encryption',
    '@libp2p/transport',
    '@libp2p/stream-multiplexing',
  ]

  readonly [serviceCapabilities]: string[] = [
    '@universal-connectivity/direct-message'
  ]

  private topologyId?: string
  private readonly components: DirectMessageComponents
  private dmPeers: Set<string> = new Set()

  constructor(components: DirectMessageComponents) {
    super()
    this.components = components
  }

  async start(): Promise<void> {
    this.topologyId = await this.components.registrar.register(DIRECT_MESSAGE_PROTOCOL, {
      onConnect: this.handleConnect.bind(this),
      onDisconnect: this.handleDisconnect.bind(this)
    })
  }

  async afterStart(): Promise<void> {
    await this.components.registrar.handle(
      DIRECT_MESSAGE_PROTOCOL,
      async ({ stream, connection }) => {
        this.receive(stream, connection)
      },
    )
  }

  stop(): void {
    if (this.topologyId != null) {
      this.components.registrar.unregister(this.topologyId)
    }
  }

  private handleConnect(peerId: PeerId): void {
    this.dmPeers.add(peerId.toString())
  }

  private handleDisconnect(peerId: PeerId): void {
    this.dmPeers.delete(peerId.toString())
  }

  isDMPeer(peerId: PeerId): boolean {
    return this.dmPeers.has(peerId.toString())
  }

  async send(peerId: PeerId, message: string): Promise<boolean> {
    if (!message) {
      throw new Error(ERRORS.EMPTY_MESSAGE)
    }

    let stream: Stream | undefined

    try {
      const conn = await this.components.connectionManager.openConnection(peerId, { signal: AbortSignal.timeout(5000) })
      if (!conn) {
        throw new Error(ERRORS.NO_CONNECTION)
      }

      // Single protocols can skip full negotiation
      const stream = await conn.newStream(DIRECT_MESSAGE_PROTOCOL, { negotiateFully: false })

      if (!stream) {
        throw new Error(ERRORS.NO_STREAM)
      }

      const datastream = pbStream(stream)

      const req: dm.DirectMessageRequest = {
        content: message,
        type: MIME_TEXT_PLAIN,
        metadata: {
          clientVersion: dmClientVersion,
          timestamp: BigInt(Date.now()),
        },
      }

      await datastream.write(req, dm.DirectMessageRequest)

      const res = await datastream.read(dm.DirectMessageResponse)

      if (!res) {
        throw new Error(ERRORS.NO_RESPONSE)
      }

      if (!res.metadata) {
        throw new Error(ERRORS.NO_METADATA)
      }

      if (res.status !== dm.Status.OK) {
        throw new Error(ERRORS.STATUS_NOT_OK(res.status))
      }
    } catch (e: any) {
      stream?.abort(e)
      throw e
    } finally {
      await stream?.close()
    }

    return true
  }

  async receive(stream: Stream, connection: Connection) {
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

    this.dispatchEvent(
      new CustomEvent(directMessageEvent, { detail })
    )
  }
}

export function directMessage() {
  return (components: DirectMessageComponents) => {
    return new DirectMessage(components)
  }
}
