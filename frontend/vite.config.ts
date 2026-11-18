import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // API_PROXY permite apuntar al stack de Docker (p. ej. http://localhost:8080)
      '/api': { target: process.env.API_PROXY ?? 'http://localhost:8000', changeOrigin: true },
    },
  },
})
