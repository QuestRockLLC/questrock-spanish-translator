import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { loadEnvFiles } from './sidecarLaunch'

const CONFIG_KEYS = [
  'OPENAI_API_KEY',
  'OPENAI_TRANSLATION_MODEL',
  'WHISPER_MODEL',
  'VAD_SILENCE_MS',
  'VAD_MAX_UTTERANCE_MS',
  'VAD_PARTIAL_INTERVAL_MS',
  'VAD_PARTIAL_WINDOW_MS',
  'QUESTROCK_LOG_TRANSCRIPTS',
  'QUESTROCK_DEBUG_AUDIO',
  'QUESTROCK_MODAL_URL',
  'QUESTROCK_MODAL_TOKEN',
] as const

export type SidecarConfig = Record<string, string>

function pickConfigFields(raw: Record<string, unknown>): SidecarConfig {
  const out: SidecarConfig = {}
  for (const key of CONFIG_KEYS) {
    const value = raw[key] ?? raw[key.toLowerCase()]
    if (typeof value === 'string' && value.length > 0) {
      out[key] = value
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      out[key] = String(value)
    }
  }
  return out
}

function fromProcessEnv(): SidecarConfig {
  const out: SidecarConfig = {}
  for (const key of CONFIG_KEYS) {
    const value = process.env[key]
    if (value) {
      out[key] = value
    }
  }
  return out
}

export function loadBakedSidecarConfig(resourcesPath: string): SidecarConfig {
  const file = path.join(resourcesPath, 'sidecar-config.json')
  if (!existsSync(file)) {
    return {}
  }
  const raw = JSON.parse(readFileSync(file, 'utf8')) as Record<string, unknown>
  return pickConfigFields(raw)
}

export async function resolveSidecarConfig(opts: {
  packaged: boolean
  repoRoot: string
  resourcesPath?: string
}): Promise<SidecarConfig> {
  if (!opts.packaged) {
    return {
      ...fromProcessEnv(),
      ...loadEnvFiles([`${opts.repoRoot}/.env`]),
    }
  }

  const baked = opts.resourcesPath ? loadBakedSidecarConfig(opts.resourcesPath) : {}
  return {
    ...fromProcessEnv(),
    ...baked,
  }
}

export function sidecarConfigError(config: SidecarConfig): string | null {
  if (config.QUESTROCK_MODAL_URL) {
    return null
  }
  if (config.OPENAI_API_KEY) {
    return null
  }
  return (
    'Modal GPU config is missing. Rebuild the installer so it includes ' +
    'sidecar-config.json, or set QUESTROCK_MODAL_URL for local dev.'
  )
}
