import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 6001,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:6002',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
