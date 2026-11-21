// Shared content from WhatsApp / SMS ("Share" -> Sahara). The service worker
// (public/share-target-sw.js) keeps it in a phone-only cache; it is read once, then deleted.

const SHARE_CACHE = 'sahara-share-v1'
const MAX_AGE_MS = 60 * 60 * 1000 // an old share is dropped, not shown to the next person on a shared phone

export interface SharedItem {
  text: string
  file: File | null
}

interface ShareMeta {
  title: string
  text: string
  url: string
  at: number
  file: { name: string; type: string } | null
}

async function readMeta(): Promise<{ cache: Cache; meta: ShareMeta } | null> {
  if (typeof caches === 'undefined') return null
  try {
    const cache = await caches.open(SHARE_CACHE)
    const response = await cache.match('/__share/meta')
    if (!response) return null
    const meta = (await response.json()) as ShareMeta
    if (Date.now() - meta.at > MAX_AGE_MS) {
      await clearShare(cache)
      return null
    }
    return { cache, meta }
  } catch {
    return null
  }
}

async function clearShare(cache: Cache): Promise<void> {
  await cache.delete('/__share/meta')
  await cache.delete('/__share/file')
}

function cleanUrl(): void {
  if (window.location.search.includes('shared=')) window.history.replaceState(null, '', window.location.pathname)
}

export async function hasPendingShare(): Promise<boolean> {
  return (await readMeta()) !== null
}

export async function takePendingShare(): Promise<SharedItem | null> {
  const found = await readMeta()
  cleanUrl()
  if (!found) return null
  const { cache, meta } = found
  let file: File | null = null
  if (meta.file) {
    const blob = await (await cache.match('/__share/file'))?.blob()
    if (blob) file = new File([blob], meta.file.name || 'shared', { type: meta.file.type })
  }
  await clearShare(cache)
  const parts = [meta.title, meta.text, meta.url].map((p) => p.trim()).filter(Boolean)
  const unique = parts.filter((p, i) => !parts.slice(0, i).some((q) => q.includes(p)))
  return { text: unique.join('\n'), file }
}
