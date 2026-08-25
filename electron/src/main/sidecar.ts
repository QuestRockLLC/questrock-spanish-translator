import { spawn, type ChildProcess } from 'node:child_process'
import { app } from 'electron'
import { createServer } from 'node:net'
import path from 'node:path'
import { loadEnvFiles, resolveSidecarLaunch } from './sidecarLaunch'

export async function pickPort(): Promise<number> {
  return await new Promise((resolve, reject) => {
    const server = createServer()
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address()
      if (addr && typeof addr === 'object') {
        const port = addr.port
        server.close(() => resolve(port))
      } else {
        reject(new Error('no port'))
      }
    })
  })
}

export function spawnSidecar(port: number): ChildProcess {
  const repoRoot = path.resolve(app.getAppPath(), '..')
  const userData = app.getPath('userData')
  const launch = resolveSidecarLaunch({
    packaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
    repoRoot,
    platform: process.platform,
    port,
  })
  const fileEnv = loadEnvFiles([
    path.join(repoRoot, '.env'),
    path.join(launch.cwd, '.env'),
    path.join(userData, '.env'),
  ])
  return spawn(launch.command, launch.args, {
    cwd: launch.cwd,
    env: {
      ...process.env,
      ...fileEnv,
      HF_HOME: path.join(userData, 'hf'),
      QUESTROCK_HOME: launch.cwd,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
}

export async function waitForHealth(port: number, timeoutMs = 180_000): Promise<void> {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/health`)
      if (res.ok) {
        return
      }
    } catch {
      await new Promise((r) => setTimeout(r, 200))
    }
  }
  throw new Error('sidecar health timeout')
}
