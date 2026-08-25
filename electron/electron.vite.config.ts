import { resolve } from 'node:path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
  },
  renderer: {
    root: resolve('src/renderer'),
    plugins: [react()],
    build: {
      rollupOptions: {
        input: {
          control: resolve('src/renderer/control/index.html'),
          overlay: resolve('src/renderer/overlay/index.html'),
        },
      },
    },
  },
})
