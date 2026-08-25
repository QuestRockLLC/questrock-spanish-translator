import { app, ipcMain } from 'electron'
import path from 'node:path'
import { GatewayClient } from './gateway'
import { registerHotkeys } from './hotkeys'
import { pickPort, spawnSidecar, waitForHealth } from './sidecar'
import { createWindows, getControl, getOverlay, setOverlayPreset } from './windows'
import type { OverlayPreset } from './overlayBounds'
import type { ServerMessage } from '../shared/protocol'

const repoRoot = path.resolve(app.getAppPath(), '..')

async function boot(): Promise<void> {
  await app.whenReady()
  const port = await pickPort()
  const child = spawnSidecar(repoRoot, port)
  child.stderr?.on('data', (chunk: Buffer) => {
    process.stderr.write(chunk)
  })
  await waitForHealth(port)
  const { control, overlay } = createWindows()
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
  registerHotkeys()
  if (process.env.ELECTRON_RENDERER_URL) {
    const base = process.env.ELECTRON_RENDERER_URL.replace(/\/$/, '')
    await control.loadURL(`${base}/control/index.html`)
    await overlay.loadURL(`${base}/overlay/index.html`)
  } else {
    await control.loadFile(path.join(__dirname, '../renderer/control/index.html'))
    await overlay.loadFile(path.join(__dirname, '../renderer/overlay/index.html'))
  }
  overlay.showInactive()
}

void boot()
