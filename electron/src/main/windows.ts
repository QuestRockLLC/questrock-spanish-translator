import { BrowserWindow, screen } from 'electron'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { overlayBounds, type OverlayPreset } from './overlayBounds'

let control: BrowserWindow | null = null
let overlay: BrowserWindow | null = null

function preloadScript(): string {
  const cjs = path.join(__dirname, '../preload/index.cjs')
  const js = path.join(__dirname, '../preload/index.js')
  const mjs = path.join(__dirname, '../preload/index.mjs')
  const chosen = [cjs, js, mjs].find((p) => existsSync(p))
  if (!chosen) {
    throw new Error(`preload script not found next to ${cjs}`)
  }
  return chosen
}

function attachPreloadDiagnostics(win: BrowserWindow, name: string): void {
  win.webContents.on('preload-error', (_event, preloadPath, error) => {
    console.error(`[preload] ${name} failed`, preloadPath, error)
  })
}

export function createWindows(): { control: BrowserWindow; overlay: BrowserWindow } {
  const preload = preloadScript()
  control = new BrowserWindow({
    width: 720,
    height: 640,
    title: 'QuestRock AI Assistant',
    show: false,
    webPreferences: {
      preload,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })
  attachPreloadDiagnostics(control, 'control')
  overlay = new BrowserWindow({
    ...overlayBounds(screen.getPrimaryDisplay().workArea, 'bottom-right'),
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: false,
    show: false,
    webPreferences: {
      preload,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })
  attachPreloadDiagnostics(overlay, 'overlay')
  overlay.setIgnoreMouseEvents(true, { forward: true })
  overlay.setAlwaysOnTop(true, 'screen-saver')
  return { control, overlay }
}

export function setOverlayPreset(preset: OverlayPreset): void {
  if (!overlay) {
    return
  }
  const b = overlayBounds(screen.getPrimaryDisplay().workArea, preset)
  overlay.setBounds(b)
}

export function toggleOverlayVisible(): void {
  if (!overlay) {
    return
  }
  if (overlay.isVisible()) {
    overlay.hide()
  } else {
    overlay.showInactive()
  }
}

export function setOverlayInteractive(interactive: boolean): void {
  overlay?.setIgnoreMouseEvents(!interactive, { forward: true })
  overlay?.setFocusable(interactive)
}

export function getOverlay(): BrowserWindow | null {
  return overlay
}

export function getControl(): BrowserWindow | null {
  return control
}
