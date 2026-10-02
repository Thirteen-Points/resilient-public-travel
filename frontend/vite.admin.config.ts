import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins: [react()], base: '/admin/',
  // The server-hosted admin always uses its own origin, independent of frontend .env.
  envDir: false,
  define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
  build: { outDir: '../backend/app/admin_static', emptyOutDir: true, rollupOptions: { input: 'admin.html' } },
})
