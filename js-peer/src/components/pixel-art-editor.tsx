import React, { useEffect, useRef, useState } from 'react'
import { usePixelArtContext, GRID_SIZE } from '@/context/pixel-art-ctx'
import { Button } from './button'
import { presets } from '@/lib/pixel-art-presets'

// Predefined color palette
const colorPalette = [
  '#000000', // Black
  '#FFFFFF', // White
  '#FF0000', // Red
  '#00FF00', // Green
  '#0000FF', // Blue
  '#FFFF00', // Yellow
  '#FF00FF', // Magenta
  '#00FFFF', // Cyan
  '#FFA500', // Orange
  '#800080', // Purple
  '#008000', // Dark Green
  '#800000', // Maroon
  '#008080', // Teal
  '#FFC0CB', // Pink
  '#A52A2A', // Brown
  '#808080', // Gray
  '#C0C0C0', // Silver
  '#000080', // Navy
  '#FFD700', // Gold
  '#4B0082', // Indigo
]

export default function PixelArtEditor() {
  const {
    pixelArtState,
    setPixel,
    selectedColor,
    setSelectedColor,
    clearCanvas,
    loadPreset,
    requestFullState,
    broadcastFullState,
  } = usePixelArtContext()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [canvasSize, setCanvasSize] = useState(512) // Default canvas size
  const [showPresets, setShowPresets] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [pixelCount, setPixelCount] = useState(0)
  const [debugMode, setDebugMode] = useState(false)
  const [showGrid, setShowGrid] = useState(true)
  const pixelSize = canvasSize / GRID_SIZE

  // Function to draw the grid and pixels
  const drawCanvas = () => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Clear the canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw the background (white)
    ctx.fillStyle = '#FFFFFF'
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    // Draw the grid lines if enabled
    if (showGrid) {
      ctx.strokeStyle = '#EEEEEE'
      ctx.lineWidth = 1

      // Draw vertical grid lines
      for (let x = 0; x <= GRID_SIZE; x++) {
        ctx.beginPath()
        ctx.moveTo(x * pixelSize, 0)
        ctx.lineTo(x * pixelSize, canvas.height)
        ctx.stroke()
      }

      // Draw horizontal grid lines
      for (let y = 0; y <= GRID_SIZE; y++) {
        ctx.beginPath()
        ctx.moveTo(0, y * pixelSize)
        ctx.lineTo(canvas.width, y * pixelSize)
        ctx.stroke()
      }
    }

    // Draw the pixels
    pixelArtState.grid.forEach((pixel) => {
      ctx.fillStyle = pixel.color
      ctx.fillRect(pixel.x * pixelSize, pixel.y * pixelSize, pixelSize, pixelSize)
    })
  }

  // Handle canvas resize
  useEffect(() => {
    const handleResize = () => {
      // Adjust canvas size based on window width
      const containerWidth = Math.min(window.innerWidth - 40, 512)
      setCanvasSize(containerWidth)
    }

    handleResize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
    }
  }, [])

  // Draw the canvas whenever the pixel art state changes or canvas size changes
  useEffect(() => {
    drawCanvas()
    setPixelCount(pixelArtState.grid.length)
  }, [pixelArtState, canvasSize, showGrid])

  // Convert mouse/touch position to grid coordinates
  const getGridCoordinates = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current
    if (!canvas) return { x: -1, y: -1 }

    const rect = canvas.getBoundingClientRect()
    const x = Math.floor((clientX - rect.left) / pixelSize)
    const y = Math.floor((clientY - rect.top) / pixelSize)

    // Ensure coordinates are within grid bounds
    if (x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE) {
      return { x, y }
    }

    return { x: -1, y: -1 }
  }

  // Mouse/touch event handlers
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDrawing(true)
    const { x, y } = getGridCoordinates(e.clientX, e.clientY)
    if (x >= 0 && y >= 0) {
      setPixel(x, y, selectedColor)
    }
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return

    const { x, y } = getGridCoordinates(e.clientX, e.clientY)
    if (x >= 0 && y >= 0) {
      setPixel(x, y, selectedColor)
    }
  }

  const handleMouseUp = () => {
    setIsDrawing(false)
  }

  const handleMouseLeave = () => {
    setIsDrawing(false)
  }

  // Touch event handlers
  const handleTouchStart = (e: React.TouchEvent<HTMLCanvasElement>) => {
    e.preventDefault()
    setIsDrawing(true)

    const touch = e.touches[0]
    const { x, y } = getGridCoordinates(touch.clientX, touch.clientY)
    if (x >= 0 && y >= 0) {
      setPixel(x, y, selectedColor)
    }
  }

  const handleTouchMove = (e: React.TouchEvent<HTMLCanvasElement>) => {
    e.preventDefault()
    if (!isDrawing) return

    const touch = e.touches[0]
    const { x, y } = getGridCoordinates(touch.clientX, touch.clientY)
    if (x >= 0 && y >= 0) {
      setPixel(x, y, selectedColor)
    }
  }

  const handleTouchEnd = () => {
    setIsDrawing(false)
  }

  // Handle loading a preset
  const handleLoadPreset = (presetName: string) => {
    const presetFunction = presets[presetName as keyof typeof presets]
    if (presetFunction) {
      loadPreset(presetFunction())
      setShowPresets(false) // Hide presets after selection
    }
  }

  // Handle refreshing the canvas
  const handleRefreshCanvas = () => {
    setIsRefreshing(true)
    requestFullState()

    // Reset the refreshing state after a timeout
    setTimeout(() => {
      setIsRefreshing(false)
    }, 2000)
  }

  // Handle broadcasting the full state
  const handleBroadcastState = () => {
    if (pixelArtState.grid.length > 0) {
      broadcastFullState()
    }
  }

  // Toggle grid visibility
  const toggleGrid = () => {
    setShowGrid(!showGrid)
  }

  return (
    <div className="flex flex-col items-center p-4">
      <h1 className="text-2xl font-bold mb-4">Collaborative Pixel Art</h1>
      <p className="text-gray-600 mb-4">Draw together with peers in real-time! 🎨</p>

      <div className="mb-4 bg-white rounded-lg shadow-md p-4">
        <canvas
          ref={canvasRef}
          width={canvasSize}
          height={canvasSize}
          className="border border-gray-300 rounded-lg cursor-crosshair"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseLeave}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
        />
        <div className="mt-2 flex justify-between items-center">
          <div className="text-sm text-gray-500">32 x 32 grid</div>
          <button
            onClick={toggleGrid}
            className={`text-sm px-2 py-1 rounded ${showGrid ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            {showGrid ? 'Hide Grid' : 'Show Grid'}
          </button>
        </div>
      </div>

      <div className="mb-4">
        <div className="flex flex-wrap justify-center gap-2 mb-4 max-w-md mx-auto">
          {colorPalette.map((color) => (
            <button
              key={color}
              className={`w-6 h-6 rounded-full border-2 ${
                selectedColor === color ? 'border-black' : 'border-gray-300'
              }`}
              style={{ backgroundColor: color }}
              onClick={() => setSelectedColor(color)}
              aria-label={`Select color ${color}`}
            />
          ))}
        </div>

        <div className="flex justify-center gap-2 mb-4">
          <Button onClick={clearCanvas} color="red" className="px-4 py-2">
            Clear Canvas
          </Button>

          <Button onClick={() => setShowPresets(!showPresets)} color="blue" className="px-4 py-2">
            {showPresets ? 'Hide Presets' : 'Show Presets'}
          </Button>

          <Button
            onClick={handleRefreshCanvas}
            color="green"
            className="px-4 py-2 flex items-center"
            disabled={isRefreshing}
          >
            {isRefreshing ? 'Refreshing...' : 'Refresh Canvas'}
            {isRefreshing && (
              <span className="ml-2 inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
            )}
          </Button>
        </div>

        {showPresets && (
          <div className="mt-4 p-4 border border-gray-200 rounded-lg bg-gray-50">
            <h3 className="text-lg font-semibold mb-2">Preset Art</h3>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
              {Object.keys(presets).map((presetName) => (
                <Button
                  key={presetName}
                  onClick={() => handleLoadPreset(presetName as keyof typeof presets)}
                  color="indigo"
                  className="px-3 py-1 text-sm"
                >
                  {presetName}
                </Button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="text-sm text-gray-500 mt-2">
        <p>Connected peers will see your artwork in real-time!</p>
        <p>New peers will automatically receive the current canvas state.</p>
        <p className="mt-1">
          Current pixel count: <span className="font-semibold">{pixelCount}</span>
        </p>

        <div className="mt-3 flex items-center">
          <input
            type="checkbox"
            id="debug-mode"
            checked={debugMode}
            onChange={() => setDebugMode(!debugMode)}
            className="mr-2"
          />
          <label htmlFor="debug-mode">Debug Mode</label>
        </div>

        {debugMode && (
          <div className="mt-2 p-3 bg-gray-100 rounded text-xs font-mono overflow-auto max-h-40">
            <p>Pixel Data (most recent 5):</p>
            <ul>
              {pixelArtState.grid
                .sort((a, b) => b.timestamp - a.timestamp)
                .slice(0, 5)
                .map((pixel, index) => (
                  <li key={index}>
                    ({pixel.x}, {pixel.y}) - {pixel.color} - {new Date(pixel.timestamp).toLocaleTimeString()} -{' '}
                    {pixel.peerId.substring(0, 8)}...
                  </li>
                ))}
            </ul>
            <div className="mt-2">
              <button
                onClick={handleBroadcastState}
                className="bg-blue-500 text-white px-2 py-1 rounded text-xs"
                disabled={pixelArtState.grid.length === 0}
              >
                Broadcast Full State
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
