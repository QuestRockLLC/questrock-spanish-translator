export type UpdateUiState =
  | { status: 'idle' }
  | { status: 'available'; version: string }
  | { status: 'downloading'; percent: number }
  | { status: 'ready'; version: string }
  | { status: 'error'; message: string }

export type AutoUpdaterLike = {
  autoDownload: boolean
  autoInstallOnAppQuit: boolean
  checkForUpdates: () => Promise<unknown>
  downloadUpdate: () => Promise<unknown>
  quitAndInstall: () => void
  on: (event: string, listener: (...args: any[]) => void) => unknown
}

export function shouldCheckForUpdates(packaged: boolean): boolean {
  return packaged
}

export function requestInstall(
  state: UpdateUiState,
  actions: { download: () => void; quitAndInstall: () => void },
): void {
  if (state.status === 'ready') {
    actions.quitAndInstall()
    return
  }
  if (state.status === 'available') {
    actions.download()
  }
}

function versionOf(info: unknown): string {
  if (info && typeof info === 'object' && 'version' in info) {
    return String((info as { version: unknown }).version)
  }
  return ''
}

export function attachUpdater(
  updater: AutoUpdaterLike,
  send: (state: UpdateUiState) => void,
): { installNow: () => void } {
  updater.autoDownload = true
  updater.autoInstallOnAppQuit = true
  let latest: UpdateUiState = { status: 'idle' }
  const set = (state: UpdateUiState) => {
    latest = state
    send(state)
  }
  updater.on('update-available', (info: unknown) => {
    set({ status: 'available', version: versionOf(info) })
  })
  updater.on('download-progress', (progress: unknown) => {
    const percent =
      progress && typeof progress === 'object' && 'percent' in progress
        ? Number((progress as { percent: unknown }).percent)
        : 0
    set({ status: 'downloading', percent: Math.round(percent) })
  })
  updater.on('update-downloaded', (info: unknown) => {
    set({ status: 'ready', version: versionOf(info) })
  })
  updater.on('error', (err: unknown) => {
    const message = err instanceof Error ? err.message : String(err)
    set({ status: 'error', message })
  })
  void updater.checkForUpdates().catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err)
    set({ status: 'error', message })
  })
  return {
    installNow: () =>
      requestInstall(latest, {
        download: () => {
          void updater.downloadUpdate()
        },
        quitAndInstall: () => updater.quitAndInstall(),
      }),
  }
}
