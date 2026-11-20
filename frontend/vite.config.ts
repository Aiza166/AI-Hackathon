import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// PWA: the app shell and Urdu audio clips are cached so the citizen flow
// keeps working on a weak or dropped connection.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Sahara (PROTOTYPE)',
        short_name: 'Sahara',
        description: 'Prototype survivor pension claims. Not an official government service.',
        theme_color: '#0f5132',
        background_color: '#ffffff',
        display: 'standalone',
        lang: 'ur',
        icons: [{ src: 'favicon.svg', sizes: 'any', type: 'image/svg+xml' }],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,mp3,ogg,opus}'],
      },
    }),
  ],
})
