import { parseEnvFile, resolveSidecarLaunch } from './sidecarLaunch'

it('parses dotenv lines', () => {
  const env = parseEnvFile('OPENAI_API_KEY=abc\n# comment\nWHISPER_MODEL=small\n')
  expect(env.OPENAI_API_KEY).toBe('abc')
  expect(env.WHISPER_MODEL).toBe('small')
})

it('uses uv in development', () => {
  const launch = resolveSidecarLaunch({
    packaged: false,
    resourcesPath: '/app/Resources',
    repoRoot: '/repo',
    platform: 'darwin',
    port: 1234,
  })
  expect(launch).toEqual({
    command: 'uv',
    args: ['run', 'questrock-sidecar', '--port', '1234'],
    cwd: '/repo',
  })
})

it('uses bundled sidecar when packaged', () => {
  const launch = resolveSidecarLaunch({
    packaged: true,
    resourcesPath: '/App.app/Contents/Resources',
    repoRoot: '/unused',
    platform: 'darwin',
    port: 9,
  })
  expect(launch.command).toBe('/App.app/Contents/Resources/sidecar/questrock-sidecar')
  expect(launch.cwd).toBe('/App.app/Contents/Resources/sidecar')
  expect(launch.args).toEqual(['--port', '9'])
})

it('uses exe suffix on windows', () => {
  const launch = resolveSidecarLaunch({
    packaged: true,
    resourcesPath: 'C:\\app\\resources',
    repoRoot: 'C:\\repo',
    platform: 'win32',
    port: 1,
  })
  expect(launch.command.endsWith('questrock-sidecar.exe')).toBe(true)
})
