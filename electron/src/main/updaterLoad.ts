import electronUpdater from 'electron-updater'
import type { AutoUpdaterLike } from './updater'

export function loadAutoUpdater(): AutoUpdaterLike {
  const pkg = electronUpdater as unknown as {
    autoUpdater?: AutoUpdaterLike
    default?: { autoUpdater?: AutoUpdaterLike }
  }
  const updater = pkg.autoUpdater ?? pkg.default?.autoUpdater
  if (updater == null) {
    throw new Error('electron-updater autoUpdater missing')
  }
  return updater
}
