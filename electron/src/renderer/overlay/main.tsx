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
    window.questrock.onEvent((raw) => {
      let msg: ServerMessage
      try {
        msg = parseServerMessage(raw)
      } catch {
        return
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
        setStatus(map[msg.state] ?? msg.state)
      }
      if (msg.type === 'error') {
        setStatus('Error')
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
