import { useCallback, useSyncExternalStore } from 'react'
import { localText, readStoredLang, storeLang, type Lang, type LocalText, type Pack } from './lang'

// One app-wide language choice. Urdu needs no download; a Sindhi or Punjabi pack is
// fetched once (its own small chunk) the first time it is chosen. Until it arrives,
// screens show Urdu, so nothing is ever blank.

const loaders: Record<Exclude<Lang, 'ur'>, () => Promise<{ default: Pack }>> = {
  sd: () => import('../i18n/sd'),
  pa: () => import('../i18n/pa'),
}

let current: Lang = readStoredLang()
const packs: Partial<Record<Lang, Pack>> = {}
const listeners = new Set<() => void>()

function notify(): void {
  listeners.forEach((fn) => fn())
}

function ensurePack(lang: Lang): void {
  if (lang === 'ur' || packs[lang]) return
  loaders[lang]()
    .then((mod) => {
      packs[lang] = mod.default
      notify()
    })
    .catch(() => {
      // Offline before the pack was ever cached: keep showing Urdu.
    })
}

ensurePack(current)

export function setLang(lang: Lang): void {
  current = lang
  storeLang(lang)
  ensurePack(lang)
  notify()
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

// Changes when the language changes and again when its pack has loaded.
const snapshot = () => `${current}:${packs[current] ? 1 : 0}`

export interface LangApi {
  lang: Lang
  setLang: (lang: Lang) => void
  /** The chosen language's line for `key` (with its lang tag), or the Urdu line. */
  text: (key: string, ur: string) => LocalText
}

export function useLang(): LangApi {
  useSyncExternalStore(subscribe, snapshot, snapshot)
  const lang = current
  const text = useCallback((key: string, ur: string) => localText(lang, packs[lang], key, ur), [lang])
  return { lang, setLang, text }
}
