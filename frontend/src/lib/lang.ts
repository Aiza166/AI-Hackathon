// Citizen screen language: Urdu (default), Sindhi or Punjabi (Shahmukhi).
// Plain TypeScript (no React) so it can be unit-tested. The text packs are fixed strings
// (src/i18n/*.ts), never generated; anything a pack does not have falls back to Urdu.
// Sindhi and Punjabi are machine-assisted translations, to be reviewed by a native speaker.
// Audio always stays Urdu (Azure has no Pakistani Punjabi voice).

export type Lang = 'ur' | 'sd' | 'pa'
export type Pack = Readonly<Record<string, string>>

export interface LangInfo {
  id: Lang
  tag: string // BCP 47 tag for the lang attribute (screen readers, fonts)
  native: string // name in its own script
  en: string
}

export const LANGS: readonly LangInfo[] = [
  { id: 'ur', tag: 'ur', native: 'اردو', en: 'Urdu' },
  { id: 'sd', tag: 'sd', native: 'سنڌي', en: 'Sindhi' },
  { id: 'pa', tag: 'pa-Arab', native: 'پنجابی', en: 'Punjabi' },
]

export const LANG_STORAGE_KEY = 'sahara.lang'

export function parseLang(value: unknown): Lang {
  return value === 'sd' || value === 'pa' ? value : 'ur'
}

export function tagFor(lang: Lang): string {
  return LANGS.find((l) => l.id === lang)?.tag ?? 'ur'
}

interface KeyValueStore {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

function storage(): KeyValueStore | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null // private mode or blocked storage: Urdu, not remembered
  }
}

export function readStoredLang(store: KeyValueStore | null = storage()): Lang {
  try {
    return parseLang(store?.getItem(LANG_STORAGE_KEY))
  } catch {
    return 'ur'
  }
}

export function storeLang(lang: Lang, store: KeyValueStore | null = storage()): void {
  try {
    store?.setItem(LANG_STORAGE_KEY, lang)
  } catch {
    // Not remembered on this phone; the choice still applies until the page reloads.
  }
}

export interface LocalText {
  text: string
  tag: string // lang attribute for the element that shows `text`
}

/** The chosen language's line for `key`, or the Urdu line when the pack does not have it. */
export function localText(lang: Lang, pack: Pack | null | undefined, key: string, ur: string): LocalText {
  const own = lang === 'ur' ? undefined : pack?.[key]
  return own ? { text: own, tag: tagFor(lang) } : { text: ur, tag: 'ur' }
}
