import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Pinned like every other frontend in this repo. This app's URL is a hardcoded launcher tile
  // in `portal` and an allowed post-login handoff origin, so a drifted port breaks the token
  // handoff, not just a bookmark.
  server: {
    port: 5173,
  },
  preview: {
    port: 5173,
  },
})
