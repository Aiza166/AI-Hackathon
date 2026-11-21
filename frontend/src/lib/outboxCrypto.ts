// Encryption for drafts and unsent claims stored on the phone (IndexedDB).
//
// A random key is made for each sign-in in this tab and imported as a non-extractable
// WebCrypto key (AES-GCM for the data, HMAC-SHA-256 for lookup keys). The raw bytes live
// only in sessionStorage, which the browser clears when the tab closes, and are removed on
// sign-out. If the key is gone (tab closed, storage cleared), stored rows cannot be read:
// they are discarded and the user is told (see outbox.ts, OUTBOX_DISCARDED).
// Residual risk: while the tab is open, someone with the unlocked phone and dev tools can
// read sessionStorage. Without the key, IndexedDB holds only ciphertext and masked CNICs.

const KEY_STORE = 'sahara.outboxKey'
const RAW_BYTES = 64 // 32 for AES-GCM, 32 for HMAC
const IV_BYTES = 12

export interface Sealed {
  iv: Uint8Array<ArrayBuffer>
  data: ArrayBuffer
}

interface Keys {
  owner: string
  aes: CryptoKey
  mac: CryptoKey
}

let cached: Promise<Keys> | null = null

function toBase64(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
}

function fromBase64(text: string): Uint8Array {
  return Uint8Array.from(atob(text), (c) => c.charCodeAt(0))
}

function readRaw(owner: string): Uint8Array | null {
  try {
    const stored = JSON.parse(sessionStorage.getItem(KEY_STORE) ?? 'null') as { owner: string; raw: string } | null
    return stored && stored.owner === owner ? fromBase64(stored.raw) : null
  } catch {
    return null
  }
}

function writeRaw(owner: string, raw: Uint8Array): void {
  try {
    sessionStorage.setItem(KEY_STORE, JSON.stringify({ owner, raw: toBase64(raw) }))
  } catch {
    // Storage blocked: the key lives in memory only, so rows will not survive a reload.
  }
}

async function importKeys(owner: string, raw: Uint8Array): Promise<Keys> {
  const aes = await crypto.subtle.importKey('raw', raw.slice(0, 32), { name: 'AES-GCM' }, false, ['encrypt', 'decrypt'])
  const mac = await crypto.subtle.importKey('raw', raw.slice(32), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  return { owner, aes, mac }
}

function keysFor(owner: string): Promise<Keys> {
  if (!cached) {
    cached = (async () => {
      let raw = readRaw(owner)
      if (!raw) {
        raw = crypto.getRandomValues(new Uint8Array(RAW_BYTES))
        writeRaw(owner, raw)
      }
      return importKeys(owner, raw)
    })()
  }
  return cached.then((keys) => {
    if (keys.owner === owner) return keys
    cached = null // another user signed in on this tab: never reuse the previous user's key
    return keysFor(owner)
  })
}

export function cryptoAvailable(): boolean {
  return typeof crypto !== 'undefined' && !!crypto.subtle
}

// Sign-out: forget the key, so anything left behind can never be read.
export function forgetKey(): void {
  cached = null
  try {
    sessionStorage.removeItem(KEY_STORE)
  } catch {
    // nothing stored
  }
}

export async function seal(owner: string, value: unknown): Promise<Sealed> {
  const { aes } = await keysFor(owner)
  const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES))
  const data = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, aes, new TextEncoder().encode(JSON.stringify(value)))
  return { iv, data }
}

// Throws if the key is not the one the row was sealed with.
export async function unseal<T>(owner: string, sealed: Sealed): Promise<T> {
  const { aes } = await keysFor(owner)
  const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: sealed.iv }, aes, sealed.data)
  return JSON.parse(new TextDecoder().decode(plain)) as T
}

// Stable lookup id for a family without storing the CNIC itself.
export async function blindId(owner: string, subject: string): Promise<string> {
  const { mac } = await keysFor(owner)
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', mac, new TextEncoder().encode(subject)))
  return Array.from(sig.slice(0, 16), (b) => b.toString(16).padStart(2, '0')).join('')
}

export function maskSubject(subject: string): string {
  return subject.length > 4 ? `****${subject.slice(-4)}` : '****'
}
