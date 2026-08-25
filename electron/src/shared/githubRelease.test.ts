import { detectOs, githubRepoFromPagesLocation, pickInstaller } from '../../../docs/download.js'

it('detects macOS', () => {
  expect(detectOs('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)')).toBe('mac')
})

it('detects Windows', () => {
  expect(detectOs('Mozilla/5.0 (Windows NT 10.0; Win64; x64)')).toBe('windows')
})

it('picks the dmg on Mac, not the zip', () => {
  const assets = [
    { name: 'QuestRock AI Assistant-0.2.0-arm64.dmg', browser_download_url: 'https://example/mac.dmg' },
    { name: 'QuestRock AI Assistant-0.2.0-arm64-mac.zip', browser_download_url: 'https://example/mac.zip' },
    { name: 'QuestRock-AI-Assistant-Setup-0.2.0.exe', browser_download_url: 'https://example/win.exe' },
  ]
  expect(pickInstaller(assets, 'mac')?.browser_download_url).toBe('https://example/mac.dmg')
})

it('picks the NSIS exe on Windows', () => {
  const assets = [
    { name: 'QuestRock AI Assistant-0.2.0-arm64.dmg', browser_download_url: 'https://example/mac.dmg' },
    { name: 'QuestRock-AI-Assistant-Setup-0.2.0.exe', browser_download_url: 'https://example/win.exe' },
  ]
  expect(pickInstaller(assets, 'windows')?.browser_download_url).toBe('https://example/win.exe')
})

it('parses project Pages URLs', () => {
  expect(githubRepoFromPagesLocation('abos.github.io', '/questrock-spanish_whispy/')).toEqual({
    owner: 'abos',
    repo: 'questrock-spanish_whispy',
  })
})
