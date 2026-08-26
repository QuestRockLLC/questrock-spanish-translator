import { describe, expect, it } from 'vitest'
import { applyTranscript, MAX_OVERLAY_LINES, Overlay } from './Overlay'
import { render, screen } from '@testing-library/react'

describe('applyTranscript', () => {
  it('updates the bottom live line in place', () => {
    const next = applyTranscript(
      {
        lines: [{ id: 'a', spanish: 'Hola', english: null, isLive: true }],
      },
      {
        id: 'a',
        original_text: 'Hola mundo',
        translated_text: 'Hello world',
        is_final: false,
      },
    )
    expect(next.lines).toHaveLength(1)
    expect(next.lines[0]?.english).toBe('Hello world')
    expect(next.lines[0]?.isLive).toBe(true)
  })

  it('appends a new live line below the previous one', () => {
    const next = applyTranscript(
      {
        lines: [{ id: 'a', spanish: 'Hola', english: 'Hello', isLive: true }],
      },
      {
        id: 'b',
        original_text: 'Gracias',
        translated_text: null,
        is_final: false,
      },
    )
    expect(next.lines).toHaveLength(2)
    expect(next.lines[0]?.spanish).toBe('Hola')
    expect(next.lines[0]?.isLive).toBe(false)
    expect(next.lines[1]?.spanish).toBe('Gracias')
    expect(next.lines[1]?.isLive).toBe(true)
  })

  it('drops the oldest lines and keeps the newest at the bottom', () => {
    let state: { lines: { id: string; spanish: string; english: string | null; isLive: boolean }[] } =
      { lines: [] }
    for (let i = 0; i < MAX_OVERLAY_LINES + 2; i += 1) {
      state = applyTranscript(state, {
        id: String(i),
        original_text: `line ${i}`,
        translated_text: `english ${i}`,
        is_final: true,
      })
    }
    expect(state.lines).toHaveLength(MAX_OVERLAY_LINES)
    expect(state.lines.at(-1)?.spanish).toBe(`line ${MAX_OVERLAY_LINES + 1}`)
    expect(state.lines[0]?.spanish).toBe('line 2')
  })
})

describe('Overlay', () => {
  it('renders older lines above and the live line at the bottom', () => {
    const { container } = render(
      <Overlay
        status="Listening"
        captions={{
          lines: [
            { id: '1', spanish: 'Hola', english: 'Hello', isLive: false },
            { id: '2', spanish: 'Mi pago es alto.', english: 'My payment is high.', isLive: true },
          ],
        }}
      />,
    )
    const rows = container.querySelectorAll('.caption-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.textContent).toContain('Hello')
    expect(rows[1]?.textContent).toContain('My payment is high.')
    expect(rows[1]?.className).toContain('live')
  })

  it('shows waiting copy when empty', () => {
    render(<Overlay status="Idle" captions={{ lines: [] }} />)
    expect(screen.getByText('Waiting for a pause in speech')).toBeTruthy()
  })
})
