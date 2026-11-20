import type { ReactNode } from 'react'
import { Icon } from '../lib/icons'
import { speak } from '../lib/speak'

// Small shared building blocks. Every citizen-facing line pairs an icon, Urdu (RTL) and small English.

interface ListenButtonProps {
  audioKey: string
  text: string
  label?: string
  compact?: boolean
}

/** The round turmeric "listen" button: the one loud element on every citizen screen. */
export function ListenButton({ audioKey, text, label = 'Listen', compact = false }: ListenButtonProps) {
  return (
    <button
      type="button"
      className={compact ? 'listen listen-compact' : 'listen'}
      aria-label={`${label} (سنیں)`}
      onClick={() => void speak(audioKey, text)}
    >
      <Icon name="speaker" size={compact ? 22 : 30} />
      {!compact && <span className="listen-text">سنیں</span>}
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
}

/** Urdu first (large, RTL), English underneath (small). */
export function Bilingual({ ur, en, as: Tag = 'span', id }: BilingualProps) {
  return (
    <Tag className="bi" id={id}>
      <span className="bi-ur" lang="ur" dir="rtl">{ur}</span>
      <span className="bi-en" lang="en">{en}</span>
    </Tag>
  )
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
