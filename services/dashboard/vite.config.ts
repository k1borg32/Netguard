/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// `npm run dev` talks to the API of the running compose stack (or API_URL).
// Same paths as behind nginx in the container: /api/v1/... and /api/health.
const api = process.env.API_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/health': { target: api, rewrite: () => '/health' },
      '/api/v1': { target: api },
    },
  },
  build: {
    // Recharts is most of the bundle (~200 kB gzipped). It is served by our own nginx, so that is fine.
    chunkSizeWarningLimit: 800,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
