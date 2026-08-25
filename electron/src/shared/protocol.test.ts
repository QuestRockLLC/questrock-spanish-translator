import { describe, it, expect } from 'vitest'
import { parseServerMessage } from './protocol'

describe('parseServerMessage', () => {
  it('parses transcript', () => {
    const msg = parseServerMessage({
      type: 'transcript',
      call_session_id: 's',
      id: 't',
      is_final: true,
      original_language: 'es',
      original_text: 'Hola',
      translated_text: 'Hello',
      confidence: 0.9,
      t0_ms: 0,
      t1_ms: 800,
    })
    expect(msg.type).toBe('transcript')
    if (msg.type === 'transcript') {
      expect(msg.original_text).toBe('Hola')
    }
  })

  it('rejects unknown type', () => {
    expect(() => parseServerMessage({ type: 'nope' })).toThrow()
  })
})
