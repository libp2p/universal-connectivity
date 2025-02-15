import { PeerId, Stream, Connection, TypedEventEmitter, Startable } from '@libp2p/interface'
import { serviceCapabilities, serviceDependencies } from '@libp2p/interface'
import type { ConnectionManager } from '@libp2p/interface-internal'
import type { Registrar } from '@libp2p/interface-internal'
import { forComponent } from './logger'

const log = forComponent('video-call')

export const VIDEO_CALL_PROTOCOL = '/universal-connectivity/video/1.0.0'

export enum CallStatus {
  IDLE = 'idle',
  INITIATING = 'initiating',
  RINGING = 'ringing',
  CONNECTED = 'connected',
  ENDED = 'ended',
  REJECTED = 'rejected'
}

export enum CallSignal {
  OFFER = 'offer',
  ANSWER = 'answer',
  ICE_CANDIDATE = 'ice-candidate',
  REJECT = 'reject',
  END_CALL = 'end-call'
}

export interface CallEvent {
  type: CallSignal
  data: any
  peerId: string
}

export interface VideoCallEvents {
  callSignal: CustomEvent<CallEvent>
  statusChange: CustomEvent<CallStatus>
  incomingCall: CustomEvent<{ peerId: PeerId }>
  callEnded: CustomEvent<void>
}

interface VideoCallComponents {
  registrar: Registrar
  connectionManager: ConnectionManager
}

export class VideoCallService extends TypedEventEmitter<VideoCallEvents> implements Startable {
  readonly [serviceDependencies]: string[] = [
    '@libp2p/identify',
    '@libp2p/connection-encryption',
    '@libp2p/transport',
    '@libp2p/stream-multiplexing',
  ]

  readonly [serviceCapabilities]: string[] = ['@universal-connectivity/video-call']

  private topologyId?: string
  private readonly components: VideoCallComponents
  private peerConnections: Map<string, RTCPeerConnection> = new Map()
  private callStatus: CallStatus = CallStatus.IDLE

  constructor(components: VideoCallComponents) {
    super()
    this.components = components
  }

  async start(): Promise<void> {
    this.topologyId = await this.components.registrar.register(VIDEO_CALL_PROTOCOL, {})
  }

  async afterStart(): Promise<void> {
    await this.components.registrar.handle(VIDEO_CALL_PROTOCOL, async ({ stream, connection }) => {
      await this.handleIncomingSignal(stream, connection)
    })
  }

  stop(): void {
    if (this.topologyId != null) {
      this.components.registrar.unregister(this.topologyId)
    }
    this.endAllCalls()
  }

  private async handleIncomingSignal(stream: Stream, connection: Connection) {
    try {
      const signal = await this.readSignal(stream)
      const peerId = connection.remotePeer.toString()

      this.dispatchEvent(new CustomEvent('callSignal', {
        detail: {
          type: signal.type,
          data: signal.data,
          peerId
        }
      }))

      if (signal.type === CallSignal.END_CALL) {
        this.endCall(peerId)
      }
    } catch (err) {
      log('Error handling incoming signal:', err)
    }
  }

  private async readSignal(stream: Stream): Promise<{ type: CallSignal; data: any }> {
    const chunks: Uint8Array[] = []
    for await (const chunk of stream.source) {
      chunks.push(chunk.subarray())
    }
    const data = new TextDecoder().decode(Buffer.concat(chunks))
    return JSON.parse(data)
  }

  private async sendSignal(peerId: PeerId, signal: { type: CallSignal; data: any }) {
    try {
      const connection = await this.components.connectionManager.openConnection(peerId)
      if (!connection) {
        throw new Error('Failed to open connection')
      }

      const stream = await connection.newStream(VIDEO_CALL_PROTOCOL)
      const data = new TextEncoder().encode(JSON.stringify(signal))
      await stream.sink([data])
    } catch (err) {
      log('Error sending signal:', err)
    }
  }

  async initiateCall(peerId: PeerId): Promise<void> {
    if (this.callStatus !== CallStatus.IDLE) {
      throw new Error('Already in a call')
    }

    const peerConnection = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    })

    this.peerConnections.set(peerId.toString(), peerConnection)
    this.updateCallStatus(CallStatus.INITIATING)

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      stream.getTracks().forEach(track => peerConnection.addTrack(track, stream))

      peerConnection.onicecandidate = async ({ candidate }) => {
        if (candidate) {
          await this.sendSignal(peerId, {
            type: CallSignal.ICE_CANDIDATE,
            data: candidate.toJSON()
          })
        }
      }

      const offer = await peerConnection.createOffer()
      await peerConnection.setLocalDescription(offer)
      await this.sendSignal(peerId, {
        type: CallSignal.OFFER,
        data: offer
      })

      this.updateCallStatus(CallStatus.RINGING)
    } catch (err) {
      this.endCall(peerId.toString())
      throw err
    }
  }

  async handleOffer(peerId: PeerId, offer: RTCSessionDescriptionInit): Promise<void> {
    if (this.callStatus !== CallStatus.IDLE) {
      await this.sendSignal(peerId, { type: CallSignal.REJECT, data: null })
      return
    }

    // Emit incoming call event
    this.dispatchEvent(new CustomEvent('incomingCall', { detail: { peerId } }))

    const peerConnection = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    })

    this.peerConnections.set(peerId.toString(), peerConnection)
    this.updateCallStatus(CallStatus.RINGING)

    peerConnection.onicecandidate = async ({ candidate }) => {
      if (candidate) {
        await this.sendSignal(peerId, {
          type: CallSignal.ICE_CANDIDATE,
          data: candidate.toJSON()
        })
      }
    }

    await peerConnection.setRemoteDescription(offer)
  }

  async acceptCall(peerId: PeerId): Promise<void> {
    const peerConnection = this.peerConnections.get(peerId.toString())
    if (!peerConnection) {
      throw new Error('No pending call')
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      stream.getTracks().forEach(track => peerConnection.addTrack(track, stream))

      const answer = await peerConnection.createAnswer()
      await peerConnection.setLocalDescription(answer)
      await this.sendSignal(peerId, {
        type: CallSignal.ANSWER,
        data: answer
      })

      this.updateCallStatus(CallStatus.CONNECTED)
    } catch (err) {
      this.endCall(peerId.toString())
      throw err
    }
  }

  async rejectCall(peerId: PeerId): Promise<void> {
    await this.sendSignal(peerId, { type: CallSignal.REJECT, data: null })
    this.endCall(peerId.toString())
  }

  async handleAnswer(peerId: string, answer: RTCSessionDescriptionInit): Promise<void> {
    const peerConnection = this.peerConnections.get(peerId)
    if (peerConnection) {
      await peerConnection.setRemoteDescription(answer)
      this.updateCallStatus(CallStatus.CONNECTED)
    }
  }

  async handleIceCandidate(peerId: string, candidate: RTCIceCandidateInit): Promise<void> {
    const peerConnection = this.peerConnections.get(peerId)
    if (peerConnection) {
      await peerConnection.addIceCandidate(candidate)
    }
  }

  async endCall(peerId: string): Promise<void> {
    const peerConnection = this.peerConnections.get(peerId)
    if (peerConnection) {
      peerConnection.getSenders().forEach(sender => {
        if (sender.track) {
          sender.track.stop()
        }
      })
      peerConnection.close()
      this.peerConnections.delete(peerId)
    }
    this.updateCallStatus(CallStatus.ENDED)
  }

  private endAllCalls(): void {
    for (const peerId of this.peerConnections.keys()) {
      this.endCall(peerId)
    }
  }

  private updateCallStatus(status: CallStatus): void {
    this.callStatus = status
    this.dispatchEvent(new CustomEvent('statusChange', { detail: status }))
  }

  getCallStatus(): CallStatus {
    return this.callStatus
  }
}

export function videoCall() {
  return (components: VideoCallComponents) => new VideoCallService(components)
}
