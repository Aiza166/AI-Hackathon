import type { IconBadge, IconName } from '../components/Icon'
import type { DocumentKind } from '../api/types'

// Icon keys sent by the backend explanations (backend/app/decision/explanations.py) -> pictograms.
export interface IconSpec {
  name: IconName
  badge?: IconBadge
}

export const ICONS: Record<string, IconSpec> = {
  check: { name: 'check' },
  people: { name: 'people' },
  'id-card': { name: 'id-card' },
  document: { name: 'document' },
  'document-alert': { name: 'document', badge: '?' },
  question: { name: 'question' },
  bank: { name: 'bank' },
  'bank-alert': { name: 'bank', badge: '!' },
  rules: { name: 'rules' },
  person: { name: 'briefcase' },
  'cloud-off': { name: 'cloud-off' },
  family: { name: 'family' },
  calendar: { name: 'calendar' },
}

export const FALLBACK_ICON: IconSpec = { name: 'info' }

export function iconFor(key: string): IconSpec {
  return ICONS[key] ?? FALLBACK_ICON
}

export const DOC_ICONS: Record<DocumentKind, IconName> = {
  death_certificate: 'certificate',
  claimant_cnic: 'id-card',
  frc: 'family',
  nikah_nama: 'rings',
}
