import { app, Menu, nativeImage, Tray, type BrowserWindow } from 'electron'
import { existsSync } from 'node:fs'
import path from 'node:path'

let tray: Tray | null = null
let quitting = false

export function isQuitting(): boolean {
  return quitting
}

export function markQuitting(): void {
  quitting = true
}

export function setupTray(getControlWindow: () => BrowserWindow | null): void {
  const icon = trayIcon()
  tray = new Tray(icon)
  tray.setToolTip('QuestRock AI Assistant')
  if (process.platform === 'darwin') {
    tray.setTitle('')
  }

  const showControl = (): void => {
    const win = getControlWindow()
    if (!win) {
      return
    }
    if (win.isMinimized()) {
      win.restore()
    }
    win.show()
    win.focus()
  }

  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: 'Show QuestRock', click: showControl },
      { type: 'separator' },
      {
        label: 'Quit',
        click: () => {
          markQuitting()
          app.quit()
        },
      },
    ]),
  )

  tray.on('click', () => {
    const win = getControlWindow()
    if (!win) {
      return
    }
    if (win.isVisible()) {
      win.hide()
    } else {
      showControl()
    }
  })
}

export function attachHideOnClose(win: BrowserWindow): void {
  win.on('close', (event) => {
    if (!isQuitting()) {
      event.preventDefault()
      win.hide()
    }
  })
}

function trayIcon(): Electron.NativeImage {
  const iconPath = resolveTrayIconPath()
  const image = nativeImage.createFromPath(iconPath)
  if (image.isEmpty()) {
    throw new Error(`Tray icon missing or unreadable: ${iconPath}`)
  }
  if (process.platform === 'darwin') {
    const sized = image.resize({ width: 16, height: 16 })
    sized.setTemplateImage(true)
    return sized
  }
  return image.resize({ width: 16, height: 16 })
}

function resolveTrayIconPath(): string {
  const candidates = [
    path.join(process.resourcesPath, 'trayTemplate.png'),
    path.join(__dirname, '../../build/trayTemplate.png'),
    path.join(app.getAppPath(), 'build/trayTemplate.png'),
  ]
  const found = candidates.find((candidate) => existsSync(candidate))
  if (found) {
    return found
  }
  return candidates[1]
}
