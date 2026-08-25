import { EventEmitter } from 'node:events'
import { attachUpdater, requestInstall, shouldCheckForUpdates, type UpdateUiState } from './updater'

it('does not check for updates unless the app is packaged', () => {
  expect(shouldCheckForUpdates(false)).toBe(false)
  expect(shouldCheckForUpdates(true)).toBe(true)
})

it('does not install when idle', () => {
  const download = vi.fn()
  const quitAndInstall = vi.fn()
  requestInstall({ status: 'idle' }, { download, quitAndInstall })
  expect(download).not.toHaveBeenCalled()
  expect(quitAndInstall).not.toHaveBeenCalled()
})

it('starts download when an update is available', () => {
  const download = vi.fn()
  const quitAndInstall = vi.fn()
  requestInstall({ status: 'available', version: '0.2.0' }, { download, quitAndInstall })
  expect(download).toHaveBeenCalledOnce()
  expect(quitAndInstall).not.toHaveBeenCalled()
})

it('quits and installs when the update is ready', () => {
  const download = vi.fn()
  const quitAndInstall = vi.fn()
  requestInstall({ status: 'ready', version: '0.2.0' }, { download, quitAndInstall })
  expect(quitAndInstall).toHaveBeenCalledOnce()
})

it('forwards updater events to the renderer', () => {
  const fake = new EventEmitter() as EventEmitter & {
    autoDownload: boolean
    autoInstallOnAppQuit: boolean
    checkForUpdates: () => Promise<unknown>
    downloadUpdate: () => Promise<unknown>
    quitAndInstall: () => void
  }
  fake.autoDownload = false
  fake.autoInstallOnAppQuit = false
  fake.checkForUpdates = vi.fn(async () => ({}))
  fake.downloadUpdate = vi.fn(async () => ({}))
  fake.quitAndInstall = vi.fn()
  const sent: UpdateUiState[] = []
  const handle = attachUpdater(fake, (state) => sent.push(state))
  expect(fake.autoDownload).toBe(true)
  expect(fake.checkForUpdates).toHaveBeenCalledOnce()

  fake.emit('update-available', { version: '0.2.0' })
  fake.emit('download-progress', { percent: 41.2 })
  fake.emit('update-downloaded', { version: '0.2.0' })
  expect(sent).toEqual([
    { status: 'available', version: '0.2.0' },
    { status: 'downloading', percent: 41 },
    { status: 'ready', version: '0.2.0' },
  ])

  handle.installNow()
  expect(fake.quitAndInstall).toHaveBeenCalledOnce()
})
