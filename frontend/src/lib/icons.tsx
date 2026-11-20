import type { ReactElement } from 'react'

// Simple line pictograms (24x24, stroke = currentColor). Hand-drawn for this prototype so the
// bundle stays tiny and the shapes stay readable at 48px on a cheap phone screen.
// Icon keys match the backend explanations (`icon` field) plus a few UI-only keys.

const PATHS: Record<string, ReactElement> = {
  check: <><circle cx="12" cy="12" r="9" /><path d="M8 12.5l3 3 5-6" /></>,
  document: <><path d="M6 3h8l5 5v13H6z" /><path d="M14 3v5h5M9 13h7M9 17h7" /></>,
  'document-alert': <><path d="M6 3h8l5 5v13H6z" /><path d="M14 3v5h5M12.5 11v4.5M12.5 18v.5" /></>,
  certificate: <><path d="M6 3h12v18H6z" /><path d="M9 7h6M9 10h6" /><circle cx="12" cy="15.5" r="2.2" /></>,
  'id-card': <><rect x="2.5" y="5" width="19" height="14" rx="2" /><circle cx="8.5" cy="10.5" r="2" /><path d="M5.5 16c.6-1.6 1.7-2.4 3-2.4s2.4.8 3 2.4M14 10h4.5M14 14h4.5" /></>,
  family: <><circle cx="7.5" cy="6.5" r="2.5" /><circle cx="16.5" cy="6.5" r="2.5" /><circle cx="12" cy="13" r="2" /><path d="M3 20c0-4 2-6.5 4.5-6.5M21 20c0-4-2-6.5-4.5-6.5M9 21c0-2.5 1.3-4.2 3-4.2s3 1.7 3 4.2" /></>,
  people: <><circle cx="9" cy="8" r="3" /><path d="M3 20c0-3.6 2.7-6 6-6s6 2.4 6 6" /><circle cx="17" cy="9" r="2.5" /><path d="M17 14c2.4 0 4 2 4 5" /></>,
  person: <><circle cx="12" cy="7.5" r="3.5" /><path d="M5 21c0-4 3-7 7-7s7 3 7 7" /><path d="M12 14l1.3 2.6L12 20l-1.3-3.4z" /></>,
  helper: <><circle cx="8" cy="7" r="2.8" /><circle cx="16" cy="7" r="2.8" /><path d="M2.5 19c0-3.4 2.4-6 5.5-6 1.6 0 3 .7 4 1.8 1-1.1 2.4-1.8 4-1.8 3.1 0 5.5 2.6 5.5 6" /></>,
  widow: <><circle cx="12" cy="9" r="3" /><path d="M7.2 11C7 5.8 9 3 12 3s5 2.8 4.8 8M5.5 21c0-4 2.9-7.2 6.5-7.2s6.5 3.2 6.5 7.2" /></>,
  son: <><circle cx="12" cy="7" r="3" /><path d="M7 21v-5a5 5 0 0 1 10 0v5" /></>,
  daughter: <><circle cx="12" cy="7" r="3" /><path d="M12 11.5L6.5 21h11z" /></>,
  ring: <><circle cx="12" cy="15" r="6" /><path d="M9 3h6l-3 4.5z" /></>,
  bank: <><path d="M3 9l9-5 9 5M5 9v9M9.7 9v9M14.3 9v9M19 9v9M3 20.5h18" /></>,
  'bank-alert': <><path d="M3 9l9-5 9 5M5 9v9M9.7 9v9M14.3 9v9M19 9v9M3 20.5h18" /><circle cx="20" cy="4" r="2.2" fill="currentColor" /></>,
  warning: <><path d="M12 3l10 18H2z" /><path d="M12 10v5M12 18v.5" /></>,
  question: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17v.5" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4M8 14h3v3H8z" /></>,
  money: <><rect x="2" y="6" width="20" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /><path d="M6 9v.01M18 15v.01" /></>,
  phone: <><rect x="7" y="2" width="10" height="20" rx="2" /><path d="M11 18h2" /></>,
  lock: <><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3M12 15v2" /></>,
  unlock: <><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 7.6-1.7M12 15v2" /></>,
  'cloud-off': <><path d="M7 18h10a4 4 0 0 0 .5-8A6 6 0 0 0 6 9.5 4.3 4.3 0 0 0 7 18z" /><path d="M3 3l18 18" /></>,
  rules: <><path d="M3.5 4.5H9a3 3 0 0 1 3 3V20a2.5 2.5 0 0 0-2.5-2.5h-6zM20.5 4.5H15a3 3 0 0 0-3 3V20a2.5 2.5 0 0 1 2.5-2.5h6z" /></>,
  speaker: <><path d="M4 9h4l5-4v14l-5-4H4z" /><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" /></>,
  'arrow-left': <path d="M19 12H5M11 6l-6 6 6 6" />,
  'arrow-right': <path d="M5 12h14M13 6l6 6-6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  eye: <><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>,
  shield: <><path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z" /><path d="M8.5 12l2.5 2.5 4.5-5" /></>,
  pen: <><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="M13.5 6.5l4 4" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  search: <><circle cx="11" cy="11" r="6" /><path d="M20 20l-4.5-4.5" /></>,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  logout: <path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10" />,
  twin: <><path d="M20 11a8 8 0 0 0-14.5-4.5L4 8M4 4v4h4" /><path d="M4 13a8 8 0 0 0 14.5 4.5L20 16M20 20v-4h-4" /></>,
  list: <path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" />,
}

export type IconName = keyof typeof PATHS

interface IconProps {
  name: string
  size?: number
  className?: string
}

/** Decorative pictogram: always pair it with visible text or an aria-label on the parent. */
export function Icon({ name, size = 24, className }: IconProps) {
  return (
    <svg
      className={className ? `icon ${className}` : 'icon'}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name] ?? PATHS.question}
    </svg>
  )
}

export const DOC_ICONS: Record<string, string> = {
  death_certificate: 'certificate',
  claimant_cnic: 'id-card',
  frc: 'family',
  nikah_nama: 'ring',
}
