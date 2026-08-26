import { contextBridge, ipcRenderer } from 'electron'
import type { ServerMessage } from '../shared/protocol'
import type { UpdateUiState } from '../main/updater'

function subscribeIpc<T>(
  channel: string,
  fn: (payload: T) => void,
): () => void {
  const handler = (_event: Electron.IpcRendererEvent, payload: T) => {
    fn(payload)
  }
  ipcRenderer.on(channel, handler)
  return () => {
    ipcRenderer.removeListener(channel, handler)
  }
}

contextBridge.exposeInMainWorld('questrock', {
  onEvent: (fn: (msg: ServerMessage) => void) =>
    subscribeIpc<ServerMessage>('questrock:event', fn),
  onUpdate: (fn: (state: UpdateUiState) => void) =>
    subscribeIpc<UpdateUiState>('questrock:update', fn),
  startCall: (deviceId: string) => ipcRenderer.invoke('questrock:start', deviceId),
  stopCall: () => ipcRenderer.invoke('questrock:stop'),
  listDevices: () => ipcRenderer.invoke('questrock:devices'),
  setOverlayPosition: (preset: string) => ipcRenderer.invoke('questrock:overlayPreset', preset),
  installUpdate: () => ipcRenderer.invoke('questrock:installUpdate'),
})
