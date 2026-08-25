import { globalShortcut } from 'electron'
import { setOverlayInteractive, toggleOverlayVisible } from './windows'

export function registerHotkeys(): void {
  globalShortcut.register('CommandOrControl+Shift+T', () => {
    toggleOverlayVisible()
  })
  globalShortcut.register('CommandOrControl+Shift+L', () => {
    setOverlayInteractive(true)
    setTimeout(() => setOverlayInteractive(false), 3000)
  })
}
