// Read a prompt aloud. Order of preference:
// 0. Sindhi or Punjabi chosen and a clip exists: /audio/<lang>/<key>.mp3 (ElevenLabs, runtime-cached),
// 1. a pre-recorded clip (/audio/<key>.mp3, cached by the PWA),
// 2. the server's neural voice (Azure ur-PK-UzmaNeural via POST /api/v1/speech/tts),
//    kept in memory and in the Cache API so each sentence is downloaded once,
// 3. the phone's own speech engine.
// The exported speak(audioKey, fallbackText) signature is stable: screens call it directly.

import { getToken } from '../api/client'
import { CLIPS } from '../i18n/audioClips'
import { currentLang } from './useLang'

const BASE: string = import.meta.env.VITE_API_BASE ?? ''
const CACHE_NAME = 'sahara-tts-v1'
const URDU_SCRIPT = /[؀-ۿ]/
const memory = new Map<string, string>() // cache key -> object URL
let serverVoiceOff = false // set after the server says TTS is not configured (or we are offline)
let current: HTMLAudioElement | null = null

type Lang = 'ur' | 'en'

export function languageOf(text: string): Lang {
  return URDU_SCRIPT.test(text) ? 'ur' : 'en'
}

async function cacheKey(lang: Lang, text: string): Promise<string> {
  try {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${lang}\n${text}`))
    const hex = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('')
    return `/tts-cache/${hex}`
  } catch {
    return `/tts-cache/${lang}/${encodeURIComponent(text).slice(0, 180)}` // no SubtleCrypto (plain http)
  }
}

async function fromCacheStorage(key: string): Promise<Blob | null> {
  try {
    if (!('caches' in window)) return null
    const hit = await (await caches.open(CACHE_NAME)).match(key)
    return hit ? await hit.blob() : null
  } catch {
    return null
  }
}

async function toCacheStorage(key: string, blob: Blob): Promise<void> {
  try {
    if (!('caches' in window)) return
    await (await caches.open(CACHE_NAME)).put(key, new Response(blob, { headers: { 'Content-Type': 'audio/mpeg' } }))
  } catch {
    // storage full or blocked: memory cache still works for this visit
  }
}

async function fromServer(lang: Lang, text: string): Promise<Blob | null> {
  const token = getToken()
  if (serverVoiceOff || !token || !navigator.onLine) return null
  try {
    const response = await fetch(`${BASE}/api/v1/speech/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ text, lang }),
    })
    if (response.status === 503) serverVoiceOff = true // not configured: stop asking this visit
    if (!response.ok) return null
    return await response.blob()
  } catch {
    return null
  }
}

async function play(url: string): Promise<boolean> {
  current?.pause()
  current = new Audio(url)
  try {
    await current.play()
    return true
  } catch {
    return false
  }
}

// The server voice for any text (no pre-recorded clip). Resolves false if it could not play.
export async function speakWithServerVoice(text: string, lang: Lang = languageOf(text)): Promise<boolean> {
  const clean = text.trim().replace(/\s+/g, ' ').slice(0, 400)
  if (!clean) return false
  const key = await cacheKey(lang, clean)
  let url = memory.get(key)
  if (!url) {
    const blob = (await fromCacheStorage(key)) ?? (await fromServer(lang, clean))
    if (!blob) return false
    void toCacheStorage(key, blob)
    url = URL.createObjectURL(blob)
    memory.set(key, url)
  }
  return play(url)
}

function speakWithPhone(text: string, lang: Lang): void {
  if (!('speechSynthesis' in window)) return
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = lang === 'ur' ? 'ur-PK' : 'en-IN'
  window.speechSynthesis.cancel()
  window.speechSynthesis.speak(utterance)
}

export async function speak(audioKey: string, fallbackText: string): Promise<void> {
  const chosen = currentLang()
  if (chosen !== 'ur' && CLIPS[chosen].has(audioKey) && (await play(`/audio/${chosen}/${audioKey}.mp3`))) return
  if (audioKey && (await play(`/audio/${audioKey}.mp3`))) return
  const lang = languageOf(fallbackText)
  if (await speakWithServerVoice(fallbackText, lang)) return
  speakWithPhone(fallbackText, lang)
}
