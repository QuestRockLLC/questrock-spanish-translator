import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { loadBakedSidecarConfig, sidecarConfigError } from './remoteConfig'

it('requires Modal URL or OpenAI key', () => {
  expect(sidecarConfigError({})).toMatch(/Modal GPU config is missing/)
  expect(sidecarConfigError({ OPENAI_API_KEY: 'sk-test' })).toBeNull()
})

it('allows Modal URL without a local OpenAI key', () => {
  expect(
    sidecarConfigError({ QUESTROCK_MODAL_URL: 'https://example.modal.run' }),
  ).toBeNull()
})

it('loads baked sidecar config from the app resources folder', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'questrock-config-'))
  writeFileSync(
    path.join(dir, 'sidecar-config.json'),
    JSON.stringify({
      QUESTROCK_MODAL_URL: 'https://example.modal.run',
      QUESTROCK_MODAL_TOKEN: 'baked-token',
    }),
  )
  expect(loadBakedSidecarConfig(dir)).toEqual({
    QUESTROCK_MODAL_URL: 'https://example.modal.run',
    QUESTROCK_MODAL_TOKEN: 'baked-token',
  })
})
