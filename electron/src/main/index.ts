import { app, dialog, ipcMain, type BrowserWindow } from 'electron'
import path from 'node:path'
import { GatewayClient } from './gateway'
import { registerHotkeys } from './hotkeys'
import { pickPort, spawnSidecar, waitForHealth } from './sidecar'
import { attachHideOnClose, markQuitting, setupTray } from './tray'
import { attachUpdater, shouldCheckForUpdates } from './updater'
import { loadAutoUpdater } from './updaterLoad'
import { createWindows, getControl, setOverlayPreset } from './windows'
import type { OverlayPreset } from './overlayBounds'
import type { ServerMessage } from '../shared/protocol'

const gotSingleInstanceLock = app.requestSingleInstanceLock()
if (!gotSingleInstanceLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    const control = getControl()
    if (!control) {
      return
    }
    if (control.isMinimized()) {
      control.restore()
    }
    control.show()
    control.focus()
  })

  void boot()
}

function rendererEntry(page: 'control' | 'overlay'): { kind: 'url' | 'file'; value: string } {
  const devBase = process.env.ELECTRON_RENDERER_URL
  if (devBase) {
    return { kind: 'url', value: `${devBase.replace(/\/$/, '')}/${page}/index.html` }
  }
  return {
    kind: 'file',
    value: path.join(__dirname, `../renderer/${page}/index.html`),
  }
}

async function loadWindow(win: BrowserWindow, page: 'control' | 'overlay'): Promise<void> {
  win.webContents.on('did-fail-load', (_event, code, desc, url) => {
    console.error(`[renderer] ${page} failed to load`, { code, desc, url })
  })
  const entry = rendererEntry(page)
  if (entry.kind === 'url') {
    await win.loadURL(entry.value)
  } else {
    await win.loadFile(entry.value)
  }
}

async function boot(): Promise<void> {
  await app.whenReady()
  setupTray(getControl)
  app.on('window-all-closed', () => {
    // Keep running in the tray after the control window is hidden.
  })
  app.on('before-quit', () => {
    markQuitting()
  })

  let port: number
  try {
    port = await pickPort()
    const child = await spawnSidecar(port)
    child.stderr?.on('data', (chunk: Buffer) => {
      process.stderr.write(chunk)
    })
    await waitForHealth(port)
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    dialog.showErrorBox('QuestRock AI Assistant', message)
    app.quit()
    return
  }

  const { control, overlay } = createWindows()
  attachHideOnClose(control)
  const gateway = new GatewayClient(`ws://127.0.0.1:${port}/v1/calls`)
  await gateway.connect()
  gateway.onMessage((msg: ServerMessage) => {
    control.webContents.send('questrock:event', msg)
    overlay.webContents.send('questrock:event', msg)
  })
  ipcMain.handle('questrock:start', async (_e, deviceId: string) => {
    gateway.startCall(deviceId)
  })
  ipcMain.handle('questrock:stop', async () => {
    gateway.stopCall()
  })
  ipcMain.handle('questrock:devices', async () => {
    const res = await fetch(`http://127.0.0.1:${port}/v1/devices`)
    return await res.json()
  })
  ipcMain.handle('questrock:overlayPreset', async (_e, preset: OverlayPreset) => {
    setOverlayPreset(preset)
  })
  if (shouldCheckForUpdates(app.isPackaged)) {
    const handle = attachUpdater(loadAutoUpdater(), (state) => {
      control.webContents.send('questrock:update', state)
    })
    ipcMain.handle('questrock:installUpdate', async () => {
      handle.installNow()
    })
  }
  registerHotkeys()
  await loadWindow(control, 'control')
  await loadWindow(overlay, 'overlay')
  control.show()
  overlay.showInactive()
}
