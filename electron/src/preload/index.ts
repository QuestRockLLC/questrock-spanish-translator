import { contextBridge, ipcRenderer } from 'electron'
import type { ServerMessage } from '../shared/protocol'

contextBridge.exposeInMainWorld('questrock', {
  onEvent: (fn: (msg: ServerMessage) => void) => {
    ipcRenderer.on('questrock:event', (_e, msg: ServerMessage) => fn(msg))
  },
  startCall: (deviceId: string) => ipcRenderer.invoke('questrock:start', deviceId),
  stopCall: () => ipcRenderer.invoke('questrock:stop'),
  listDevices: () => ipcRenderer.invoke('questrock:devices'),
  setOverlayPosition: (preset: string) => ipcRenderer.invoke('questrock:overlayPreset', preset),
})
