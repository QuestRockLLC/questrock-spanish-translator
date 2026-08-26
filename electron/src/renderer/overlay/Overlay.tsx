import type { CSSProperties } from 'react'
import { useEffect, useRef } from 'react'
import './overlay.css'

export type CaptionLine = {
  id: string
  spanish: string
  english: string | null
  isLive: boolean
}

export type OverlayCaptionState = {
  lines: CaptionLine[]
}

export type OverlayProps = {
  status: string
  captions: OverlayCaptionState
}

const wrap: CSSProperties = {
  fontFamily: 'system-ui, sans-serif',
  background: 'rgba(12, 16, 22, 0.94)',
  color: '#eef3f8',
  borderRadius: 10,
  padding: '8px 12px 10px',
  border: '1px solid #3d4a5c',
  WebkitAppRegion: 'drag',
  boxSizing: 'border-box',
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
} as CSSProperties

function englishFor(line: CaptionLine): string {
  return line.english ?? line.spanish
}

function showSpanishVerifier(line: CaptionLine): boolean {
  return Boolean(line.english && line.spanish && line.english !== line.spanish)
}

export function Overlay({ status, captions }: OverlayProps) {
  const stackRef = useRef<HTMLDivElement | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ block: 'end', behavior: 'smooth' })
  }, [captions.lines])

  return (
    <div style={wrap}>
      <div className="overlay-header">
        <span>QuestRock</span>
        <span className="overlay-status">{status}</span>
      </div>
      <div ref={stackRef} className="caption-stack">
        {captions.lines.length === 0 ? (
          <div className="caption-empty">Waiting for a pause in speech</div>
        ) : (
          captions.lines.map((line, index) => {
            const isBottom = index === captions.lines.length - 1
            return (
              <div
                key={line.id}
                ref={isBottom ? bottomRef : undefined}
                className={`caption-row${isBottom ? ' live' : ' history'}`}
              >
                {showSpanishVerifier(line) ? (
                  <div className="caption-spanish spanish">{line.spanish}</div>
                ) : null}
                <div className={`caption-english english${isBottom ? ' live' : ''}`}>
                  {englishFor(line)}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

export const MAX_OVERLAY_LINES = 5

export function applyTranscript(
  state: OverlayCaptionState,
  msg: {
    id: string
    original_text: string
    translated_text: string | null
    is_final: boolean
  },
): OverlayCaptionState {
  const idx = state.lines.findIndex((line) => line.id === msg.id)
  if (idx >= 0) {
    const lines = state.lines.map((line, i) =>
      i === idx
        ? {
            ...line,
            spanish: msg.original_text,
            english: msg.translated_text ?? line.english,
            isLive: !msg.is_final,
          }
        : line,
    )
    return { lines: trimLines(lines) }
  }

  const committed = state.lines.map((line) =>
    line.isLive
      ? {
          ...line,
          isLive: false,
          english: line.english ?? line.spanish,
        }
      : line,
  )
  const lines = [
    ...committed,
    {
      id: msg.id,
      spanish: msg.original_text,
      english: msg.translated_text,
      isLive: !msg.is_final,
    },
  ]
  return { lines: trimLines(lines) }
}

function trimLines(lines: CaptionLine[]): CaptionLine[] {
  return lines.slice(-MAX_OVERLAY_LINES)
}
