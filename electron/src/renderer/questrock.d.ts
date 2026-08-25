export type OverlayPreset = 'bottom-right' | 'bottom-center' | 'top-right'

export type QuestrockApi = {
  onEvent: (fn: (msg: unknown) => void) => void
  startCall: (deviceId: string) => Promise<void>
  stopCall: () => Promise<void>
  listDevices: () => Promise<{ devices: Array<{ id: string; name: string; kind: string }> }>
  setOverlayPosition: (preset: OverlayPreset) => Promise<void>
}

declare global {
  interface Window {
    questrock: QuestrockApi
  }
}

export {}
