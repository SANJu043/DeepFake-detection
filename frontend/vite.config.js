import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const bypassHtml = (req) => {
  if (req.headers.accept && req.headers.accept.includes('text/html')) {
    return '/index.html'
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/auth': { target: 'http://127.0.0.1:8000', bypass: bypassHtml },
      '/videos': { target: 'http://127.0.0.1:8000', bypass: bypassHtml },
      '/jobs': { target: 'http://127.0.0.1:8000', bypass: bypassHtml },
      '/attestations': { target: 'http://127.0.0.1:8000', bypass: bypassHtml },
      '/verify': { target: 'http://127.0.0.1:8000', bypass: bypassHtml },
      '/admin': { target: 'http://127.0.0.1:8000', bypass: bypassHtml },
      '/shares': { target: 'http://127.0.0.1:8000', bypass: bypassHtml },
      '/health': { target: 'http://127.0.0.1:8000', bypass: bypassHtml },
    },
  },
})
