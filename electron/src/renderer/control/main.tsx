import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import type { ServerMessage } from '../../shared/protocol'
import { parseServerMessage } from '../../shared/protocol'
import type { OverlayPreset } from '../../main/overlayBounds'
import type { UpdateUiState } from '../../main/updater'
import { UpdateBanner } from './UpdateBanner'

type Row = { id: string; original: string; translated: string; confidence: number }

function displayTranslation(original: string, translated: string | null): string {
  return translated ?? original
}

function App() {
  const [devices, setDevices] = useState<Array<{ id: string; name: string }>>([])
  const [deviceId, setDeviceId] = useState('')
  const [status, setStatus] = useState('Idle')
  const [history, setHistory] = useState<Row[]>([])
  const [preset, setPreset] = useState<OverlayPreset>('bottom-right')
  const [update, setUpdate] = useState<UpdateUiState>({ status: 'idle' })

  useEffect(() => {
    const api = window.questrock
    if (!api) {
      setStatus('preload missing')
      return
    }
    const offUpdate = api.onUpdate((state) => setUpdate(state))
    void api.listDevices().then((payload) => {
      setDevices(payload.devices)
      if (payload.devices[0]) {
        setDeviceId(payload.devices[0].id)
      }
    })
    const offEvent = api.onEvent((raw) => {
      let msg: ServerMessage
      try {
        msg = parseServerMessage(raw)
      } catch {
        return
      }
      if (msg.type === 'session_started') {
        setStatus('Starting session')
        setHistory([])
      }
      if (msg.type === 'status') {
        if (msg.state === 'idle') {
          setStatus('Idle')
          return
        }
        setStatus(msg.detail ? `${msg.state} (${msg.detail})` : msg.state)
      }
      if (msg.type === 'error') {
        setStatus(msg.message)
      }
      if (msg.type === 'transcript') {
        const row: Row = {
          id: msg.id,
          original: msg.original_text,
          translated: displayTranslation(msg.original_text, msg.translated_text),
          confidence: msg.confidence,
        }
        if (msg.is_final) {
          setHistory((h) => [...h.filter((entry) => entry.id !== msg.id), row].slice(-50))
        }
      }
    })
    return () => {
      offEvent()
      offUpdate()
    }
  }, [])

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 20, color: '#1d1d1f' }}>
      <h1 style={{ fontSize: 20 }}>QuestRock AI Assistant</h1>
      <UpdateBanner state={update} onInstall={() => void window.questrock?.installUpdate()} />
      <p>Status: {status}</p>
      <label>
        Loopback device
        <select value={deviceId} onChange={(e) => setDeviceId(e.target.value)} style={{ marginLeft: 8 }}>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </label>
      <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
        <button
          type="button"
          onClick={() => {
            setStatus('Starting session')
            void window.questrock?.startCall(deviceId).catch((err: unknown) => {
              setStatus(err instanceof Error ? err.message : 'Start failed')
            })
          }}
        >
          Start Spanish mode
        </button>
        <button
          type="button"
          onClick={() => {
            setStatus('Idle')
            void window.questrock?.stopCall().catch((err: unknown) => {
              setStatus(err instanceof Error ? err.message : 'Stop failed')
            })
          }}
        >
          Stop
        </button>
      </div>
      <fieldset style={{ marginTop: 16, border: '1px solid #d1d1d6' }}>
        <legend>Overlay position</legend>
        {(['bottom-right', 'bottom-center', 'top-right'] as OverlayPreset[]).map((p) => (
          <label key={p} style={{ marginRight: 12 }}>
            <input
              type="radio"
              name="preset"
              checked={preset === p}
              onChange={() => {
                setPreset(p)
                void window.questrock?.setOverlayPosition(p)
              }}
            />
            {p}
          </label>
        ))}
      </fieldset>
      <h2 style={{ fontSize: 16, marginTop: 20 }}>Transcripts</h2>
      <ul>
        {history.map((row) => (
          <li key={row.id} style={{ marginBottom: 14 }}>
            <div style={{ whiteSpace: 'pre-wrap' }}>{row.original}</div>
            <div style={{ whiteSpace: 'pre-wrap' }}>
              <strong>{row.translated}</strong> ({Math.round(row.confidence * 100)}%)
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

const el = document.getElementById('root')
if (el) {
  createRoot(el).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}
