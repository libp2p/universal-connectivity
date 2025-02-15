import React, { useEffect, useRef, useState } from 'react'
import { useLibp2pContext } from '../context/ctx'
import { CallStatus, CallSignal } from '../lib/video-call'
import { peerIdFromString } from '@libp2p/peer-id'
import { Button } from './button'
import { forComponent } from '../lib/logger'

const log = forComponent('video-call-component')

interface VideoCallProps {
  peerId: string
  onClose: () => void
}

export const VideoCall: React.FC<VideoCallProps> = ({ peerId, onClose }) => {
  const { libp2p } = useLibp2pContext()
  const localVideoRef = useRef<HTMLVideoElement>(null)
  const remoteVideoRef = useRef<HTMLVideoElement>(null)
  const [callStatus, setCallStatus] = useState<CallStatus>(CallStatus.IDLE)
  const [isMuted, setIsMuted] = useState(false)
  const [isVideoEnabled, setIsVideoEnabled] = useState(true)

  useEffect(() => {
    const handleCallSignal = async (evt: CustomEvent<any>) => {
      const { type, data, peerId: signalPeerId } = evt.detail
      if (signalPeerId !== peerId) return

      switch (type) {
        case CallSignal.OFFER:
          await libp2p.services.videoCall.handleOffer(peerIdFromString(peerId), data)
          break
        case CallSignal.ANSWER:
          await libp2p.services.videoCall.handleAnswer(peerId, data)
          break
        case CallSignal.ICE_CANDIDATE:
          await libp2p.services.videoCall.handleIceCandidate(peerId, data)
          break
        case CallSignal.REJECT:
          setCallStatus(CallStatus.REJECTED)
          setTimeout(onClose, 2000)
          break
        case CallSignal.END_CALL:
          setCallStatus(CallStatus.ENDED)
          setTimeout(onClose, 2000)
          break
      }
    }

    const handleStatusChange = (evt: CustomEvent<CallStatus>) => {
      setCallStatus(evt.detail)
      if (evt.detail === CallStatus.ENDED || evt.detail === CallStatus.REJECTED) {
        setTimeout(onClose, 2000)
      }
    }

    libp2p.services.videoCall.addEventListener('callSignal', handleCallSignal as any)
    libp2p.services.videoCall.addEventListener('statusChange', handleStatusChange as any)

    return () => {
      libp2p.services.videoCall.removeEventListener('callSignal', handleCallSignal as any)
      libp2p.services.videoCall.removeEventListener('statusChange', handleStatusChange as any)
    }
  }, [libp2p, peerId, onClose])

  const handleAcceptCall = async () => {
    try {
      await libp2p.services.videoCall.acceptCall(peerIdFromString(peerId))
    } catch (err) {
      log('Error accepting call:', err)
    }
  }

  const handleRejectCall = async () => {
    try {
      await libp2p.services.videoCall.rejectCall(peerIdFromString(peerId))
    } catch (err) {
      log('Error rejecting call:', err)
    }
  }

  const handleEndCall = async () => {
    try {
      await libp2p.services.videoCall.endCall(peerId)
    } catch (err) {
      log('Error ending call:', err)
    }
  }

  const toggleMute = () => {
    if (localVideoRef.current && localVideoRef.current.srcObject instanceof MediaStream) {
      const audioTracks = localVideoRef.current.srcObject.getAudioTracks()
      audioTracks.forEach(track => {
        track.enabled = !track.enabled
      })
      setIsMuted(!isMuted)
    }
  }

  const toggleVideo = () => {
    if (localVideoRef.current && localVideoRef.current.srcObject instanceof MediaStream) {
      const videoTracks = localVideoRef.current.srcObject.getVideoTracks()
      videoTracks.forEach(track => {
        track.enabled = !track.enabled
      })
      setIsVideoEnabled(!isVideoEnabled)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg p-4 max-w-4xl w-full">
        <div className="flex justify-between mb-4">
          <h2 className="text-xl font-bold">
            Video Call {callStatus !== CallStatus.IDLE && `- ${callStatus}`}
          </h2>
          <Button onClick={handleEndCall} color="red">End Call</Button>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="relative">
            <video
              ref={localVideoRef}
              autoPlay
              playsInline
              muted
              className="w-full rounded-lg bg-gray-900"
            />
            <div className="absolute bottom-2 left-2">Local</div>
          </div>
          <div className="relative">
            <video
              ref={remoteVideoRef}
              autoPlay
              playsInline
              className="w-full rounded-lg bg-gray-900"
            />
            <div className="absolute bottom-2 left-2">Remote</div>
          </div>
        </div>

        <div className="flex justify-center space-x-4">
          {callStatus === CallStatus.RINGING && (
            <>
              <Button onClick={handleAcceptCall} color="green">Accept</Button>
              <Button onClick={handleRejectCall} color="red">Reject</Button>
            </>
          )}
          {callStatus === CallStatus.CONNECTED && (
            <>
              <Button onClick={toggleMute}>
                {isMuted ? 'Unmute' : 'Mute'}
              </Button>
              <Button onClick={toggleVideo}>
                {isVideoEnabled ? 'Disable Video' : 'Enable Video'}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
