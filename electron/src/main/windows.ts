import { BrowserWindow, screen } from 'electron'
import path from 'node:path'
import { overlayBounds, type OverlayPreset } from './overlayBounds'

let control: BrowserWindow | null = null
let overlay: BrowserWindow | null = null

export function createWindows(): { control: BrowserWindow; overlay: BrowserWindow } {
  control = new BrowserWindow({
    width: 720,
    height: 640,
    title: 'QuestRock AI Assistant',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  overlay = new BrowserWindow({
    ...overlayBounds(screen.getPrimaryDisplay().workArea, 'bottom-right'),
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: false,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
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
