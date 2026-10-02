import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, '.', 'VITE_')
  return {
  plugins: [react(), {
    name: 'public-build-identity',
    generateBundle() {
      const candidate = (environment.VITE_BUILD_SHA || '').toLowerCase()
      this.emitFile({ type: 'asset', fileName: 'build-info.json', source: JSON.stringify({
        commit_sha: /^[0-9a-f]{40}$/.test(candidate) ? candidate : null,
        source: /^[0-9a-f]{40}$/.test(candidate) ? 'VITE_BUILD_SHA' : 'unknown',
      }) })
    },
  }],
  server: { port: 5173 },
  }
})
