import React, { createContext, useContext, useEffect, useState } from 'react'
import { useLibp2pContext } from './ctx'
import type { Message } from '@libp2p/interface'
import { PIXEL_ART_TOPIC } from '@/lib/constants'
import { forComponent } from '@/lib/logger'

const log = forComponent('pixel-art-context')

// Define the pixel grid size
export const GRID_SIZE = 32

// Define the pixel art data structure
export interface PixelData {
  x: number
  y: number
  color: string
  timestamp: number
  peerId: string
}

export interface PixelArtState {
  grid: PixelData[]
}

export interface PixelArtContextInterface {
  pixelArtState: PixelArtState
  setPixel: (x: number, y: number, color: string) => void
  selectedColor: string
  setSelectedColor: (color: string) => void
  clearCanvas: () => void
  loadPreset: (pixels: PixelData[]) => void
  requestFullState: () => void
  broadcastFullState: () => void
}

export const pixelArtContext = createContext<PixelArtContextInterface>({
  pixelArtState: { grid: [] },
  setPixel: () => {},
  selectedColor: '#000000',
  setSelectedColor: () => {},
  clearCanvas: () => {},
  loadPreset: () => {},
  requestFullState: () => {},
  broadcastFullState: () => {},
})

export const usePixelArtContext = () => {
  return useContext(pixelArtContext)
}

export const PixelArtProvider = ({ children }: { children: React.ReactNode }) => {
  const [pixelArtState, setPixelArtState] = useState<PixelArtState>({ grid: [] })
  const [selectedColor, setSelectedColor] = useState<string>('#000000')
  const { libp2p } = useLibp2pContext()

  // Function to update a pixel and broadcast the change
  const setPixel = (x: number, y: number, color: string) => {
    if (!libp2p) return

    const pixelData: PixelData = {
      x,
      y,
      color,
      timestamp: Date.now(),
      peerId: libp2p.peerId.toString(),
    }

    // Update local state
    updatePixelState(pixelData)

    // Broadcast the change to other peers
    const pixelDataString = JSON.stringify(pixelData)
    libp2p.services.pubsub.publish(PIXEL_ART_TOPIC, new TextEncoder().encode(pixelDataString))
  }

  // Function to clear the canvas and broadcast the change
  const clearCanvas = () => {
    if (!libp2p) return

    // Update local state
    setPixelArtState({ grid: [] })

    // Broadcast the clear action to other peers
    const clearAction = JSON.stringify({ action: 'clear', timestamp: Date.now(), peerId: libp2p.peerId.toString() })
    libp2p.services.pubsub.publish(PIXEL_ART_TOPIC, new TextEncoder().encode(clearAction))
  }

  // Function to load a preset and broadcast the change
  const loadPreset = (pixels: PixelData[]) => {
    if (!libp2p) return

    // Clear the canvas first
    clearCanvas()

    // Update local state with all preset pixels
    setPixelArtState({ grid: pixels })

    // Broadcast each pixel to other peers
    pixels.forEach((pixel) => {
      const pixelDataString = JSON.stringify({
        ...pixel,
        peerId: libp2p.peerId.toString(), // Use the current peer ID for broadcasting
      })
      libp2p.services.pubsub.publish(PIXEL_ART_TOPIC, new TextEncoder().encode(pixelDataString))
    })
  }

  // Function to request the full state from other peers
  const requestFullState = () => {
    if (!libp2p) return

    const requestMessage = JSON.stringify({
      action: 'requestState',
      timestamp: Date.now(),
      peerId: libp2p.peerId.toString(),
    })

    log(`Requesting full pixel art state from peers`)
    libp2p.services.pubsub.publish(PIXEL_ART_TOPIC, new TextEncoder().encode(requestMessage))
  }

  // Function to send the full state to a requesting peer
  const sendFullState = (requestingPeerId: string) => {
    if (!libp2p) return

    // Even if we have no pixels, send an empty state to prevent repeated requests
    const fullStateMessage = JSON.stringify({
      action: 'fullState',
      timestamp: Date.now(),
      peerId: libp2p.peerId.toString(),
      targetPeerId: requestingPeerId,
      state: pixelArtState,
    })

    log(`Sending full pixel art state to peer ${requestingPeerId}`)
    libp2p.services.pubsub.publish(PIXEL_ART_TOPIC, new TextEncoder().encode(fullStateMessage))
  }

  // Function to broadcast the full state to all peers
  const broadcastFullState = () => {
    if (!libp2p) return

    const fullStateMessage = JSON.stringify({
      action: 'fullState',
      timestamp: Date.now(),
      peerId: libp2p.peerId.toString(),
      // No targetPeerId means broadcast to all
      state: pixelArtState,
    })

    log(`Broadcasting full pixel art state to all peers (${pixelArtState.grid.length} pixels)`)
    libp2p.services.pubsub.publish(PIXEL_ART_TOPIC, new TextEncoder().encode(fullStateMessage))
  }

  // Function to update the pixel state
  const updatePixelState = (pixelData: PixelData) => {
    setPixelArtState((prevState) => {
      // Create a copy of the current grid
      const updatedGrid = [...prevState.grid]

      // Find if the pixel already exists
      const existingPixelIndex = updatedGrid.findIndex((pixel) => pixel.x === pixelData.x && pixel.y === pixelData.y)

      if (existingPixelIndex !== -1) {
        // Update existing pixel if the new one is more recent
        if (pixelData.timestamp > updatedGrid[existingPixelIndex].timestamp) {
          updatedGrid[existingPixelIndex] = pixelData
        }
      } else {
        // Add new pixel
        updatedGrid.push(pixelData)
      }

      return { grid: updatedGrid }
    })
  }

  // Handle incoming pixel art messages
  const handlePixelArtMessage = (evt: CustomEvent<Message>) => {
    if (evt.detail.topic !== PIXEL_ART_TOPIC || evt.detail.type !== 'signed') {
      return
    }

    try {
      const data = new TextDecoder().decode(evt.detail.data)
      const parsedData = JSON.parse(data)
      const senderPeerId = evt.detail.from.toString()

      // Handle clear action
      if (parsedData.action === 'clear') {
        log(`Received clear canvas action from ${senderPeerId}`)
        setPixelArtState({ grid: [] })
        return
      }

      // Handle state request
      if (parsedData.action === 'requestState') {
        const requestingPeerId = parsedData.peerId
        if (requestingPeerId !== libp2p.peerId.toString()) {
          log(`Received state request from peer ${requestingPeerId}`)

          // Add a small random delay to prevent all peers from responding at once
          setTimeout(() => {
            sendFullState(requestingPeerId)
          }, Math.random() * 1000)
        }
        return
      }

      // Handle full state
      if (parsedData.action === 'fullState') {
        // Only process if we're the target or if it's a broadcast to all
        if (parsedData.targetPeerId === libp2p.peerId.toString() || !parsedData.targetPeerId) {
          log(`Received full state from peer ${senderPeerId} with ${parsedData.state.grid.length} pixels`)

          // Only update if the received state has pixels and either:
          // 1. Our canvas is empty, or
          // 2. The received state is newer based on the most recent pixel timestamp
          if (
            parsedData.state.grid.length > 0 &&
            (pixelArtState.grid.length === 0 ||
              (parsedData.state.grid.length > 0 &&
                Math.max(...parsedData.state.grid.map((p: PixelData) => p.timestamp)) >
                  Math.max(...pixelArtState.grid.map((p) => p.timestamp || 0))))
          ) {
            log(`Updating canvas with received state (${parsedData.state.grid.length} pixels)`)
            setPixelArtState(parsedData.state)
          } else {
            log(`Ignoring received state (${parsedData.state.grid.length} pixels) as our state is newer or equal`)
          }
        }
        return
      }

      // Handle pixel update
      const pixelData = parsedData as PixelData
      log(
        `Received pixel update at (${pixelData.x}, ${pixelData.y}) with color ${pixelData.color} from ${senderPeerId}`,
      )
      updatePixelState(pixelData)
    } catch (error) {
      console.error('Error parsing pixel art message:', error)
    }
  }

  // Subscribe to the pixel art topic when the component mounts
  useEffect(() => {
    if (!libp2p) return

    // Subscribe to the pixel art topic
    libp2p.services.pubsub.subscribe(PIXEL_ART_TOPIC)

    // Add event listener for incoming messages
    libp2p.services.pubsub.addEventListener('message', handlePixelArtMessage)

    // Wait a moment before requesting the current state to ensure subscription is active
    const timer = setTimeout(() => {
      requestFullState()
    }, 1000)

    return () => {
      // Cleanup when the component unmounts
      clearTimeout(timer)
      libp2p.services.pubsub.removeEventListener('message', handlePixelArtMessage)
      libp2p.services.pubsub.unsubscribe(PIXEL_ART_TOPIC)
    }
  }, [libp2p])

  // Listen for peer discovery events to request state from new peers
  useEffect(() => {
    if (!libp2p) return

    const handlePeerDiscovery = (event: any) => {
      const peerId = event.detail.id.toString()
      log(`Discovered peer: ${peerId}`)

      // Only request state if we don't have any pixels yet
      if (pixelArtState.grid.length === 0) {
        // Add a small delay to ensure the peer has time to set up
        setTimeout(() => {
          requestFullState()
        }, 2000)
      }
    }

    libp2p.addEventListener('peer:discovery', handlePeerDiscovery)

    return () => {
      libp2p.removeEventListener('peer:discovery', handlePeerDiscovery)
    }
  }, [libp2p, pixelArtState.grid.length])

  // Periodically broadcast the full state to ensure all peers are in sync
  useEffect(() => {
    if (!libp2p) return

    // Only broadcast if we have pixels to share
    if (pixelArtState.grid.length === 0) return

    const interval = setInterval(() => {
      broadcastFullState()
    }, 30000) // Every 30 seconds

    return () => {
      clearInterval(interval)
    }
  }, [libp2p, pixelArtState.grid.length])

  return (
    <pixelArtContext.Provider
      value={{
        pixelArtState,
        setPixel,
        selectedColor,
        setSelectedColor,
        clearCanvas,
        loadPreset,
        requestFullState,
        broadcastFullState,
      }}
    >
      {children}
    </pixelArtContext.Provider>
  )
}
