/* Web Share Target for Sahara (PROTOTYPE).
 * "Share" from WhatsApp, SMS or the gallery sends a POST to /share-target. The installed app's
 * service worker catches it here (nothing reaches a server), keeps the shared text and one file
 * in a phone-only cache, and opens the app at /?shared=1. Scam Shield reads it once and deletes it.
 * Loaded by the Workbox service worker through importScripts (vite.config.ts).
 */
const SHARE_CACHE = 'sahara-share-v1'
const MAX_FILE_BYTES = 8 * 1024 * 1024
const MAX_TEXT = 2000
const FILE_TYPES = /^(image|audio)\/|^video\/(mp4|webm|3gpp)$/

function clip(value, max) {
  return typeof value === 'string' ? value.slice(0, max) : ''
}

async function keepShare(request) {
  const form = await request.formData()
  const cache = await caches.open(SHARE_CACHE)
  const meta = {
    title: clip(form.get('title'), 300),
    text: clip(form.get('text'), MAX_TEXT),
    url: clip(form.get('url'), MAX_TEXT),
    at: Date.now(),
    file: null,
  }
  const file = form.getAll('media').find((f) => typeof f !== 'string' && f.size > 0)
  if (file && file.size <= MAX_FILE_BYTES && FILE_TYPES.test(file.type)) {
    await cache.put('/__share/file', new Response(file, { headers: { 'Content-Type': file.type } }))
    meta.file = { name: clip(file.name, 100), type: file.type }
  } else {
    await cache.delete('/__share/file')
  }
  await cache.put('/__share/meta', new Response(JSON.stringify(meta), { headers: { 'Content-Type': 'application/json' } }))
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (event.request.method !== 'POST' || url.origin !== self.location.origin || url.pathname !== '/share-target') return
  // A share from the phone arrives as a user navigation (Sec-Fetch-Site none or same-origin). A form on another
  // website posting here is cross-site: ignore it so no one can plant text in Scam Shield.
  const site = event.request.headers.get('Sec-Fetch-Site')
  if (site === 'cross-site' || site === 'same-site') return
  event.respondWith(
    keepShare(event.request)
      .catch(() => undefined) // the app still opens; the citizen can paste instead
      .then(() => Response.redirect('/?shared=1', 303)),
  )
})
