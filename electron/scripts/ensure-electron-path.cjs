const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const electronRoot = path.join(__dirname, '..', 'node_modules', 'electron')
const dist = path.join(electronRoot, 'dist')
const pathFile = path.join(electronRoot, 'path.txt')
const { version } = require(path.join(electronRoot, 'package.json'))

const platformPath =
  {
    darwin: 'Electron.app/Contents/MacOS/Electron',
    mas: 'Electron.app/Contents/MacOS/Electron',
    win32: 'electron.exe',
  }[os.platform()] ?? 'electron'

const binary = path.join(dist, platformPath)
const frameworks = path.join(dist, 'Electron.app/Contents/Frameworks/Electron Framework.framework')

function writePathTxt() {
  fs.writeFileSync(pathFile, platformPath)
}

async function main() {
  const intact =
    fs.existsSync(binary) && (os.platform() !== 'darwin' || fs.existsSync(frameworks))
  if (intact) {
    writePathTxt()
    return
  }

  const { downloadArtifact } = require('@electron/get')
  const zipPath = await downloadArtifact({
    version,
    artifactName: 'electron',
    platform: process.platform,
    arch: process.arch,
  })
  fs.rmSync(dist, { recursive: true, force: true })
  fs.mkdirSync(dist, { recursive: true })
  execFileSync('unzip', ['-o', zipPath, '-d', dist], { stdio: 'inherit' })
  writePathTxt()
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
