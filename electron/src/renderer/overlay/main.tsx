import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { applyTranscript, Overlay, type OverlayCaptionState } from './Overlay'
import type { ServerMessage } from '../../shared/protocol'
import { parseServerMessage } from '../../shared/protocol'

const emptyCaptions: OverlayCaptionState = { lines: [] }

function OverlayApp() {
  const [status, setStatus] = useState('Idle')
  const [captions, setCaptions] = useState<OverlayCaptionState>(emptyCaptions)

  useEffect(() => {
    const api = window.questrock
    if (!api) {
      return
    }
    const offEvent = api.onEvent((raw) => {
      let msg: ServerMessage
      try {
        msg = parseServerMessage(raw)
      } catch {
        return
      }
      if (msg.type === 'session_started') {
        setStatus('Starting')
        setCaptions(emptyCaptions)
      }
      if (msg.type === 'status') {
        const map: Record<string, string> = {
          loading_model: 'Loading model',
          listening: 'Listening',
          transcribing: 'Transcribing',
          translating: 'Translating',
          error: 'Error',
          idle: 'Idle',
        }
        const label = map[msg.state] ?? msg.state
        setStatus(msg.detail ? `${label} (${msg.detail})` : label)
        if (msg.state === 'idle') {
          setCaptions(emptyCaptions)
        }
      }
      if (msg.type === 'error') {
        setStatus(msg.message)
      }
      if (msg.type === 'transcript') {
        setCaptions((prev) => applyTranscript(prev, msg))
      }
    })
    return offEvent
  }, [])

  return <Overlay status={status} captions={captions} />
}

const el = document.getElementById('root')
if (el) {
  createRoot(el).render(
    <StrictMode>
      <OverlayApp />
    </StrictMode>,
  )
}
