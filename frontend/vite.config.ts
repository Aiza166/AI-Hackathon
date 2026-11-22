import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// PWA: the app shell and Urdu audio clips are cached so the citizen flow
// keeps working on a weak or dropped connection.
// Dev and preview forward /api to a local FastAPI server. Set VITE_PROXY_TARGET to point a second
// local stack elsewhere, e.g. VITE_PROXY_TARGET=http://localhost:8010 for the E2E backend.
const proxy = { '/api': process.env.VITE_PROXY_TARGET || 'http://localhost:8000' }

export default defineConfig({
  server: { proxy },
  preview: { proxy },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Sahara (PROTOTYPE)',
        short_name: 'Sahara',
        description: 'Prototype survivor pension claims. Not an official government service.',
        theme_color: '#17204d',
        background_color: '#f3f5fb',
        display: 'standalone',
        lang: 'ur',
        icons: [{ src: 'favicon.svg', sizes: 'any', type: 'image/svg+xml' }],
        // "Share" from WhatsApp / SMS / gallery opens Scam Shield prefilled (installed app only).
        // public/share-target-sw.js receives the POST inside the service worker; nothing goes to a server.
        share_target: {
          action: '/share-target',
          method: 'POST',
          enctype: 'multipart/form-data',
          params: {
            title: 'title',
            text: 'text',
            url: 'url',
            files: [{ name: 'media', accept: ['image/*', 'audio/*', 'video/mp4', 'video/webm', 'video/3gpp'] }],
          },
        },
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,mp3,ogg,opus}'],
        // The Sentry SDK chunk is optional and loaded on demand: never precache it for offline use.
        globIgnores: ['**/sentry-*.js', 'audio/sd/**', 'audio/pa/**'],
        // Sindhi and Punjabi clips stay out of the app shell: fetched on first listen, then kept.
        runtimeCaching: [
          {
            urlPattern: ({ url }: { url: URL }) => /^\/audio\/(sd|pa)\//.test(url.pathname),
            handler: 'CacheFirst',
            options: { cacheName: 'sahara-local-audio-v1', expiration: { maxEntries: 120 }, rangeRequests: true },
          },
        ],
        // Runs before Workbox's own routes so the share POST is caught first.
        importScripts: ['share-target-sw.js'],
      },
    }),
  ],
})
