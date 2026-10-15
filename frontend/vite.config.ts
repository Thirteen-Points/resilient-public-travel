import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, '.', ['VITE_', 'CF_PAGES_COMMIT_SHA'])
  return {
  plugins: [react(), tailwindcss(), {
    name: 'public-build-identity',
    generateBundle() {
      const source = environment.VITE_BUILD_SHA ? 'VITE_BUILD_SHA' : 'CF_PAGES_COMMIT_SHA'
      const candidate = (environment.VITE_BUILD_SHA || environment.CF_PAGES_COMMIT_SHA || '').toLowerCase()
      this.emitFile({ type: 'asset', fileName: 'build-info.json', source: JSON.stringify({
        commit_sha: /^[0-9a-f]{40}$/.test(candidate) ? candidate : null,
        source: /^[0-9a-f]{40}$/.test(candidate) ? source : 'unknown',
      }) })
    },
  }],
  server: { port: 5173 },
  }
})
