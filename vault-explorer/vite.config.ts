import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    include: ['react-force-graph-3d', 'three', 'three-spritetext'],
    exclude: []
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          three: ['three'],
          graph: ['react-force-graph-3d', 'three-spritetext'],
        }
      }
    }
  }
})
