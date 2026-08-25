export type OverlayPreset = 'bottom-right' | 'bottom-center' | 'top-right'

export type DisplayRect = { x: number; y: number; width: number; height: number }

export type Bounds = { x: number; y: number; width: number; height: number }

export function overlayBounds(display: DisplayRect, preset: OverlayPreset): Bounds {
  const width = 400
  const height = 140
  const margin = 16
  if (preset === 'bottom-center') {
    return {
      x: display.x + Math.round((display.width - width) / 2),
      y: display.y + display.height - height - margin,
      width,
      height,
    }
  }
  if (preset === 'top-right') {
    return {
      x: display.x + display.width - width - margin,
      y: display.y + margin,
      width,
      height,
    }
  }
  return {
    x: display.x + display.width - width - margin,
    y: display.y + display.height - height - margin,
    width,
    height,
  }
}
