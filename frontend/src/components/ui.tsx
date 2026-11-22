import type { ReactNode } from 'react'
import { Icon } from '../lib/icons'
import { CLIPS } from '../i18n/audioClips'
import { speak } from '../lib/speak'
import { useLang } from '../lib/useLang'

// Small shared building blocks. Every citizen-facing line pairs an icon, Urdu (RTL) and small English.

interface ListenButtonProps {
  audioKey: string
  text: string
  label?: string
  compact?: boolean
}

/** The round turmeric "listen" button: the one loud element on every citizen screen. */
export function ListenButton({ audioKey, text, label = 'Listen', compact = false }: ListenButtonProps) {
  const { lang } = useLang()
  // Say so when this line will be read in Urdu: another language is chosen but it has no clip for this key.
  const urduTag = lang !== 'ur' && !CLIPS[lang].has(audioKey)
  const classes = ['listen', compact ? 'listen-compact' : '', urduTag ? 'listen-tagged' : ''].filter(Boolean).join(' ')
  return (
    <button
      type="button"
      className={classes}
      aria-label={urduTag ? `${label} (in Urdu) (سنیں)` : `${label} (سنیں)`}
      onClick={() => void speak(audioKey, text)}
    >
      <Icon name="speaker" size={compact ? 22 : 30} />
      {!compact && <span className="listen-text">سنیں</span>}
      {urduTag && (
        <span className="listen-tag">
          <span lang="ur" dir="rtl">اردو</span> <span lang="en" dir="ltr">Urdu</span>
        </span>
      )}
    </button>
  )
}

type Tone = 'ok' | 'attn' | 'risk' | 'info' | 'quiet'

interface PictogramProps {
  name: string
  tone?: Tone
  size?: 'sm' | 'md' | 'lg'
}

export function Pictogram({ name, tone = 'info', size = 'md' }: PictogramProps) {
  const px = size === 'lg' ? 44 : size === 'sm' ? 22 : 30
  return (
    <span className={`picto picto-${size} tone-${tone}`}>
      <Icon name={name} size={px} />
    </span>
  )
}

interface BilingualProps {
  ur: string
  en: string
  as?: 'h1' | 'h2' | 'h3' | 'p' | 'span'
  id?: string
  /** Text key in the Sindhi/Punjabi packs; without it the line always stays Urdu. */
  k?: string
}

/** Urdu (or the chosen Sindhi/Punjabi line) first, large and RTL; English underneath, small. */
export function Bilingual({ ur, en, as: Tag = 'span', id, k }: BilingualProps) {
  const { text } = useLang()
  const local = k ? text(k, ur) : { text: ur, tag: 'ur' }
  return (
    <Tag className="bi" id={id}>
      <span className="bi-ur" lang={local.tag} dir="rtl">{local.text}</span>
      <span className="bi-en" lang="en">{en}</span>
    </Tag>
  )
}

interface LocalProps {
  k: string
  ur: string
  className?: string
}

/** One fixed citizen line in the chosen language (Urdu fallback), right-to-left. */
export function Local({ k, ur, className }: LocalProps) {
  const { text } = useLang()
  const local = text(k, ur)
  return <span lang={local.tag} dir="rtl" className={className}>{local.text}</span>
}

interface BadgeProps {
  tone: Tone
  children: ReactNode
}

export function Badge({ tone, children }: BadgeProps) {
  return <span className={`badge tone-${tone}`}>{children}</span>
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p className="note note-risk" role="alert">
      <Icon name="warning" size={20} />
      <span>{message}</span>
    </p>
  )
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return <p className="loading" role="status">{label}…</p>
}

/** Route/status colour mapping shared by staff screens. */
export function toneFor(value: string | null | undefined): Tone {
  switch (value) {
    case 'AUTO_APPROVE':
    case 'auto_approved':
    case 'approved':
    case 'live':
    case 'active':
      return 'ok'
    case 'ASK_PROOF':
    case 'proof_requested':
    case 'draft':
      return 'attn'
    case 'rejected':
    case 'UNSURE':
      return 'risk'
    case 'retired':
    case 'withdrawn':
      return 'quiet'
    default:
      return 'info'
  }
}

export function humanize(value: string): string {
  return value.replace(/_/g, ' ').toLowerCase()
}

export function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
