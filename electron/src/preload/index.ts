import { contextBridge, ipcRenderer } from 'electron'
import type { ServerMessage } from '../shared/protocol'
import type { UpdateUiState } from '../main/updater'

contextBridge.exposeInMainWorld('questrock', {
  onEvent: (fn: (msg: ServerMessage) => void) => {
    ipcRenderer.on('questrock:event', (_e, msg: ServerMessage) => fn(msg))
  },
  onUpdate: (fn: (state: UpdateUiState) => void) => {
    ipcRenderer.on('questrock:update', (_e, state: UpdateUiState) => fn(state))
  },
  startCall: (deviceId: string) => ipcRenderer.invoke('questrock:start', deviceId),
  stopCall: () => ipcRenderer.invoke('questrock:stop'),
  listDevices: () => ipcRenderer.invoke('questrock:devices'),
  setOverlayPosition: (preset: string) => ipcRenderer.invoke('questrock:overlayPreset', preset),
  installUpdate: () => ipcRenderer.invoke('questrock:installUpdate'),
})
