import { sidecarConfigError } from './remoteConfig'

it('requires an OpenAI key for packaged sidecar env', () => {
  expect(sidecarConfigError({})).toMatch(/OpenAI API key is missing/)
  expect(sidecarConfigError({ OPENAI_API_KEY: 'sk-test' })).toBeNull()
})

it('allows Modal URL without a local OpenAI key', () => {
  expect(
    sidecarConfigError({ QUESTROCK_MODAL_URL: 'https://example.modal.run' }),
  ).toBeNull()
})
