import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // While developing, any request starting with /api goes to the Python server
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})