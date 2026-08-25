import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'

export function parseEnvFile(contents: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const raw of contents.split(/\r?\n/)) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) {
      continue
    }
    const eq = line.indexOf('=')
    if (eq <= 0) {
      continue
    }
    const key = line.slice(0, eq).trim()
    let value = line.slice(eq + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    out[key] = value
  }
  return out
}

export function loadEnvFiles(files: string[]): Record<string, string> {
  const merged: Record<string, string> = {}
  for (const file of files) {
    if (!existsSync(file)) {
      continue
    }
    Object.assign(merged, parseEnvFile(readFileSync(file, 'utf8')))
  }
  return merged
}

export type SidecarLaunch = {
  command: string
  args: string[]
  cwd: string
}

export function resolveSidecarLaunch(opts: {
  packaged: boolean
  resourcesPath: string
  repoRoot: string
  platform: NodeJS.Platform
  port: number
}): SidecarLaunch {
  if (!opts.packaged) {
    return {
      command: 'uv',
      args: ['run', 'questrock-sidecar', '--port', String(opts.port)],
      cwd: opts.repoRoot,
    }
  }
  const cwd = path.join(opts.resourcesPath, 'sidecar')
  const binary =
    opts.platform === 'win32' ? 'questrock-sidecar.exe' : 'questrock-sidecar'
  return {
    command: path.join(cwd, binary),
    args: ['--port', String(opts.port)],
    cwd,
  }
}
