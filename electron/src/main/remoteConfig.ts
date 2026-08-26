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

async function fetchRemoteConfig(url: string): Promise<SidecarConfig> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = process.env.QUESTROCK_DEVICE_TOKEN
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const res = await fetch(url, { headers })
  if (!res.ok) {
    throw new Error(`QuestRock config fetch failed (${res.status})`)
  }
  const body = (await res.json()) as Record<string, unknown>
  return pickConfigFields(body)
}

export async function resolveSidecarConfig(opts: {
  packaged: boolean
  repoRoot: string
}): Promise<SidecarConfig> {
  if (!opts.packaged) {
    return {
      ...fromProcessEnv(),
      ...loadEnvFiles([`${opts.repoRoot}/.env`]),
    }
  }

  const url = process.env.QUESTROCK_CONFIG_URL
  const remote = url ? await fetchRemoteConfig(url) : {}
  return {
    ...fromProcessEnv(),
    ...remote,
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
    'OpenAI API key is missing. Set QUESTROCK_MODAL_URL (Modal GPU inference), ' +
    'QUESTROCK_CONFIG_URL (cloud config), or OPENAI_API_KEY as a system environment variable.'
  )
}
