#!/usr/bin/env node
const fs = require('node:fs')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '..')
const OUT = path.join(ROOT, 'packaging', 'dist', 'sidecar-config.json')

function parseEnvFile(contents) {
  const out = {}
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

function fromRepoEnv() {
  const envPath = path.join(ROOT, '.env')
  if (!fs.existsSync(envPath)) {
    return {}
  }
  return parseEnvFile(fs.readFileSync(envPath, 'utf8'))
}

const repo = fromRepoEnv()
const url = (process.env.QUESTROCK_MODAL_URL || repo.QUESTROCK_MODAL_URL || '').trim()
const token = (process.env.QUESTROCK_MODAL_TOKEN || repo.QUESTROCK_MODAL_TOKEN || '').trim()

if (!url || !token) {
  console.error(
    'Packaged builds need QUESTROCK_MODAL_URL and QUESTROCK_MODAL_TOKEN. ' +
      'Set them in the repo-root .env (local dist) or GitHub Actions secrets (release).',
  )
  process.exit(1)
}

fs.mkdirSync(path.dirname(OUT), { recursive: true })
fs.writeFileSync(
  OUT,
  `${JSON.stringify(
    {
      QUESTROCK_MODAL_URL: url,
      QUESTROCK_MODAL_TOKEN: token,
    },
    null,
    2,
  )}\n`,
)
console.log(`wrote ${OUT}`)
