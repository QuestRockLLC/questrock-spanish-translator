import { describe, it, expect } from 'vitest'
import { overlayBounds } from './overlayBounds'

describe('overlayBounds', () => {
  const display = { x: 0, y: 0, width: 1920, height: 1080 }
  it('bottom-right compact card', () => {
    const b = overlayBounds(display, 'bottom-right')
    expect(b.width).toBeGreaterThanOrEqual(380)
    expect(b.width).toBeLessThanOrEqual(420)
    expect(b.x + b.width).toBe(1920 - 16)
    expect(b.y + b.height).toBe(1080 - 16)
  })
})
