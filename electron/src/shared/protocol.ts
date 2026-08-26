export type ServerMessage =
  | {
      type: 'session_started'
      call_session_id: string
      device_id: string
    }
  | {
      type: 'status'
      call_session_id: string
      state: string
      detail?: string
    }
  | {
      type: 'transcript'
      call_session_id: string
      id: string
      is_final: boolean
      original_language: string
      original_text: string
      translated_text: string | null
      confidence: number
      t0_ms: number
      t1_ms: number
    }
  | {
      type: 'error'
      code: string
      message: string
    }

export function parseServerMessage(raw: unknown): ServerMessage {
  if (!raw || typeof raw !== 'object' || !('type' in raw)) {
    throw new Error('invalid message')
  }
  const msg = raw as { type: string }
  if (msg.type === 'session_started' || msg.type === 'status' || msg.type === 'transcript' || msg.type === 'error') {
    return raw as ServerMessage
  }
  throw new Error('unknown type')
}
