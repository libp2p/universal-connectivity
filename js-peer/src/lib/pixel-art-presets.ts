import { PixelData } from '@/context/pixel-art-ctx'

// Helper function to create pixel data from a pattern
const createPixelArt = (
  pattern: string[],
  colorMap: Record<string, string>,
  offsetX: number = 0,
  offsetY: number = 0,
): PixelData[] => {
  const pixels: PixelData[] = []
  const timestamp = Date.now()

  pattern.forEach((row, y) => {
    row.split('').forEach((char, x) => {
      if (char !== ' ' && colorMap[char]) {
        pixels.push({
          x: x + offsetX,
          y: y + offsetY,
          color: colorMap[char],
          timestamp,
          peerId: 'preset', // Mark as preset
        })
      }
    })
  })

  return pixels
}

// Space Invader 1 - Classic
export const spaceInvader1 = () => {
  const pattern = ['   ██   ', '    ██  ', '   ████ ', '  ██ ██ ', '  █████ ', '   █ █  ', '  █   █ ']

  const colorMap: Record<string, string> = {
    '█': '#00FF00', // Green
  }

  return createPixelArt(pattern, colorMap, 12, 12)
}

// Space Invader 2 - Detailed
export const spaceInvader2 = () => {
  const pattern = [
    '  █    █  ',
    '   █  █   ',
    '  ██████  ',
    ' ████████ ',
    '██ ████ ██',
    '██████████',
    '█ ██  ██ █',
    '   █  █   ',
  ]

  const colorMap: Record<string, string> = {
    '█': '#FF00FF', // Magenta
  }

  return createPixelArt(pattern, colorMap, 11, 12)
}

// Pac-Man - Improved
export const pacMan = () => {
  const pattern = [
    '  ●●●●   ',
    ' ●●●●●●  ',
    '●●●●●●   ',
    '●●●●     ',
    '●●●      ',
    '●●●●     ',
    '●●●●●●   ',
    ' ●●●●●●  ',
    '  ●●●●   ',
  ]

  const colorMap: Record<string, string> = {
    '●': '#FFFF00', // Yellow
  }

  return createPixelArt(pattern, colorMap, 12, 11)
}

// Ghost - Blinky (Red)
export const ghost = () => {
  const pattern = [
    '  ██████  ',
    ' ████████ ',
    '██████████',
    '██████████',
    '██████████',
    '██████████',
    '██████████',
    '██ ██  ██ ',
    '   ██  ██ ',
  ]

  const colorMap: Record<string, string> = {
    '█': '#FF0000', // Red
  }

  return createPixelArt(pattern, colorMap, 11, 11)
}

// Ghost - Inky (Blue)
export const blueGhost = () => {
  const pattern = [
    '  ██████  ',
    ' ████████ ',
    '██████████',
    '██████████',
    '██████████',
    '██████████',
    '██████████',
    '██ ██  ██ ',
    '   ██  ██ ',
  ]

  const colorMap: Record<string, string> = {
    '█': '#00FFFF', // Cyan
  }

  return createPixelArt(pattern, colorMap, 11, 11)
}

// Cherry
export const cherry = () => {
  const pattern = [
    '    ██   ',
    '   ████  ',
    '    ██   ',
    '    █    ',
    '   ██    ',
    '  ███    ',
    ' ████    ',
    ' ████    ',
    '  ███    ',
    '   ██    ',
    '    █    ',
    '     █   ',
    '    ███  ',
    '   █████ ',
    '  ███████',
    '  ███████',
    '   █████ ',
  ]

  const colorMap: Record<string, string> = {
    '█': '#FF0000', // Red
  }

  return createPixelArt(pattern, colorMap, 11, 7)
}

// Mario
export const mario = () => {
  const pattern = [
    '  rrrrr  ',
    ' rrrrrrr ',
    ' bbsssb  ',
    'bssbsssb ',
    'bssbssbb ',
    'bbbssssb ',
    '  sssss  ',
    ' rrbrrb  ',
    'rrrbbbrrr',
    'bbbbbbbbb',
    'bbbbbbbb ',
    ' bb  bb  ',
    'ooo  ooo ',
  ]

  const colorMap: Record<string, string> = {
    r: '#FF0000', // Red
    b: '#A52A2A', // Brown
    s: '#FFC0CB', // Skin/Pink
    o: '#FFA500', // Orange
  }

  return createPixelArt(pattern, colorMap, 11, 9)
}

// Mushroom
export const mushroom = () => {
  const pattern = [
    '   wwww   ',
    ' wwrrrrww ',
    'wrrwwwwrrw',
    'wrwwwwwwrw',
    'wrwwwwwwrw',
    'wrrrrrrrrw',
    'wrrrrrrrrw',
    ' wwwsswww ',
    '   ssss   ',
    '  sssss   ',
    '  sssss   ',
  ]

  const colorMap: Record<string, string> = {
    r: '#FF0000', // Red
    w: '#FFFFFF', // White
    s: '#FFC0CB', // Skin/Pink
  }

  return createPixelArt(pattern, colorMap, 11, 10)
}

// Heart
export const heart = () => {
  const pattern = [' rr   rr ', 'rrrr rrrr', 'rrrrrrrr ', 'rrrrrrrr ', ' rrrrrr  ', '  rrrr   ', '   rr    ']

  const colorMap: Record<string, string> = {
    r: '#FF0000', // Red
  }

  return createPixelArt(pattern, colorMap, 11, 12)
}

// Star
export const star = () => {
  const pattern = [
    '    y    ',
    '    y    ',
    '   yyy   ',
    'yyyyyyyy ',
    ' yyyyyy  ',
    '  yyyy   ',
    ' yy yy   ',
    'y    y   ',
  ]

  const colorMap: Record<string, string> = {
    y: '#FFFF00', // Yellow
  }

  return createPixelArt(pattern, colorMap, 11, 12)
}

// Link (from Zelda)
export const link = () => {
  const pattern = [
    '  ggggg  ',
    ' ggggggg ',
    ' gsssssg ',
    'sssssssss',
    'sssssssss',
    'sssbsbsss',
    ' sssssss ',
    '  gbbg   ',
    ' gggbggg ',
    'ggggbgggg',
    'ggggbgggg',
    ' ggbbbgg ',
    '  ggggg  ',
    ' bb  bb  ',
    'bbbb bbbb',
  ]

  const colorMap: Record<string, string> = {
    g: '#008000', // Green
    s: '#FFC0CB', // Skin/Pink
    b: '#A52A2A', // Brown
  }

  return createPixelArt(pattern, colorMap, 11, 8)
}

// Creeper (Minecraft)
export const creeper = () => {
  const pattern = ['gggggggg', 'gggggggg', 'gg    gg', 'gg    gg', 'g      g', 'g  gg  g', 'g gggg g', 'gggggggg']

  const colorMap: Record<string, string> = {
    g: '#008000', // Green
  }

  return createPixelArt(pattern, colorMap, 12, 12)
}

// Sword
export const sword = () => {
  const pattern = [
    '    g    ',
    '    g    ',
    '    g    ',
    '    g    ',
    '    g    ',
    '    g    ',
    '   ggg   ',
    '   bbb   ',
    '    b    ',
  ]

  const colorMap: Record<string, string> = {
    g: '#C0C0C0', // Silver
    b: '#A52A2A', // Brown
  }

  return createPixelArt(pattern, colorMap, 11, 11)
}

// Export all presets
export const presets = {
  'Space Invader 1': spaceInvader1,
  'Space Invader 2': spaceInvader2,
  'Pac-Man': pacMan,
  'Red Ghost': ghost,
  'Blue Ghost': blueGhost,
  Cherry: cherry,
  Mario: mario,
  Mushroom: mushroom,
  Heart: heart,
  Star: star,
  Link: link,
  Creeper: creeper,
  Sword: sword,
}
