import type { CSSProperties } from 'react'

export type OverlayProps = {
  status: string
  originalText: string
  translatedText: string | null
}

const wrap: CSSProperties = {
  fontFamily: 'system-ui, sans-serif',
  background: 'rgba(12, 16, 22, 0.92)',
  color: '#eef3f8',
  borderRadius: 10,
  padding: '10px 12px',
  border: '1px solid #3d4a5c',
  WebkitAppRegion: 'drag',
} as CSSProperties

export function Overlay({ status, originalText, translatedText }: OverlayProps) {
  const english =
    originalText === '' && translatedText == null
      ? 'Waiting for speech'
      : (translatedText ?? 'Translation unavailable')
  return (
    <div style={wrap}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#8fb4d9', marginBottom: 6 }}>
        <span>QuestRock</span>
        <span style={{ color: '#6ee7a8' }}>{status}</span>
      </div>
      {originalText ? <div className="spanish" style={{ fontSize: 11, color: '#9db0c4', marginBottom: 4 }}>{originalText}</div> : null}
      <div className="english" style={{ fontSize: 15, lineHeight: 1.3, fontWeight: 600 }}>{english}</div>
    </div>
  )
}
