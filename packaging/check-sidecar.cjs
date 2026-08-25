const fs = require('node:fs')
const path = require('node:path')

const expected = process.argv[2]
if (process.platform !== expected) {
  console.error(
    `Build this installer on ${expected}. This machine is ${process.platform}. The Python sidecar is OS-native (faster-whisper / torch).`,
  )
  process.exit(1)
}

const sidecarDir = path.join(__dirname, '..', 'packaging', 'dist', 'sidecar')
const binary =
  process.platform === 'win32' ? 'questrock-sidecar.exe' : 'questrock-sidecar'
if (!fs.existsSync(path.join(sidecarDir, binary))) {
  console.error(
    `Missing ${path.join(sidecarDir, binary)}. Run: uv sync --extra packaging && uv run python packaging/build_sidecar.py`,
  )
  process.exit(1)
}
