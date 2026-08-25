import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Overlay } from './Overlay'
import type { ServerMessage } from '../../shared/protocol'
import { parseServerMessage } from '../../shared/protocol'

function OverlayApp() {
  const [status, setStatus] = useState('Idle')
  const [originalText, setOriginalText] = useState('')
  const [translatedText, setTranslatedText] = useState<string | null>(null)

  useEffect(() => {
    const api = window.questrock
    if (!api) {
      return
    }
    api.onEvent((raw) => {
      let msg: ServerMessage
      try {
        msg = parseServerMessage(raw)
      } catch {
        return
      }
      if (msg.type === 'session_started') {
        setStatus('Starting')
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
          setOriginalText('')
          setTranslatedText(null)
        }
      }
      if (msg.type === 'error') {
        setStatus(msg.message)
      }
      if (msg.type === 'transcript') {
        setOriginalText(msg.original_text)
        setTranslatedText(msg.translated_text)
      }
    })
  }, [])

  return <Overlay status={status} originalText={originalText} translatedText={translatedText} />
}

const el = document.getElementById('root')
if (el) {
  createRoot(el).render(
    <StrictMode>
      <OverlayApp />
    </StrictMode>,
  )
}
