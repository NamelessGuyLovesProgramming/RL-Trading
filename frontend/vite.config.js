import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: '../static',  // Build direkt in FastAPI static/ Ordner
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Optimale Chunk-Strategie
        manualChunks: {
          'vendor': ['svelte'],
          'chart': ['lightweight-charts']
        }
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      // WebSocket Proxy
      '/ws': {
        target: 'ws://localhost:8003',
        ws: true,
        changeOrigin: true
      },
      // API Proxy
      '/api': {
        target: 'http://localhost:8003',
        changeOrigin: true
      }
    }
  }
})
