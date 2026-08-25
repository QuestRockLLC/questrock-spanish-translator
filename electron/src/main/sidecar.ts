import { spawn, type ChildProcess } from 'node:child_process'
import { createServer } from 'node:net'
import path from 'node:path'

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

export function spawnSidecar(repoRoot: string, port: number): ChildProcess {
  return spawn('uv', ['run', 'questrock-sidecar', '--port', String(port)], {
    cwd: repoRoot,
    env: { ...process.env },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
}

export async function waitForHealth(port: number, timeoutMs = 30_000): Promise<void> {
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

export function repoRootFromElectron(): string {
  return path.resolve(__dirname, '../../../../')
}
