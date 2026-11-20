import type { ReactElement } from 'react'

// Pictograms drawn for Sahara during the hackathon: simple, thick-line shapes on a 48x48 grid
// so they stay readable on a small, cheap screen. Colour comes from the surrounding text.

const PERSON_BODY = 'M10 42c0-8 6-14 14-14s14 6 14 14'
const CHILD_BODY = 'M14 42c0-7 4-12 10-12s10 5 10 12'

const SHAPES = {
  check: (
    <>
      <circle cx="24" cy="24" r="20" />
      <path d="M14 25l7 7 13-15" />
    </>
  ),
  question: (
    <>
      <circle cx="24" cy="24" r="20" />
      <path d="M18 18a6 6 0 1 1 8 5.6c-1.4.6-2 1.6-2 3V29" />
      <circle cx="24" cy="35" r="1.8" className="fill" />
    </>
  ),
  info: (
    <>
      <circle cx="24" cy="24" r="20" />
      <path d="M24 22v12" />
      <circle cx="24" cy="15" r="1.8" className="fill" />
    </>
  ),
  person: (
    <>
      <circle cx="24" cy="15" r="7" />
      <path d={PERSON_BODY} />
    </>
  ),
  people: (
    <>
      <circle cx="17" cy="16" r="6" />
      <path d="M5 40c0-7 5-12 12-12s12 5 12 12" />
      <circle cx="33" cy="14" r="5" />
      <path d="M29 27c1.3-.4 2.6-.5 4-.5 6 0 10 4.5 10 11" />
    </>
  ),
  family: (
    <>
      <circle cx="13" cy="12" r="5" />
      <path d="M5 37c0-7 3.6-12 8-12s8 5 8 12" />
      <circle cx="35" cy="12" r="5" />
      <path d="M27 37c0-7 3.6-12 8-12s8 5 8 12" />
      <circle cx="24" cy="26" r="4" />
      <path d="M18 43c0-5 2.7-8 6-8s6 3 6 8" />
    </>
  ),
  // Adult woman: dupatta covers the head and falls to the shoulders.
  woman: (
    <>
      <path d="M12 31c-1.5-3-2-6-2-10C10 12 16 5 24 5s14 7 14 16c0 4-.5 7-2 10" className="fill-soft" />
      <circle cx="24" cy="18" r="6" />
      <path d={PERSON_BODY} />
    </>
  ),
  // Girl: smaller body, long hair to the shoulders on both sides.
  girl: (
    <>
      <path d="M18.5 17c-1.5 3-1.5 7 .5 10M29.5 17c1.5 3 1.5 7-.5 10" />
      <circle cx="24" cy="18" r="5.5" />
      <path d={CHILD_BODY} />
    </>
  ),
  // Boy: smaller body, short filled hair cap, nothing covering the sides.
  boy: (
    <>
      <circle cx="24" cy="18" r="5.5" />
      <path d="M18.5 17a5.5 5.5 0 0 1 11 0z" className="fill" />
      <path d={CHILD_BODY} />
    </>
  ),
  'id-card': (
    <>
      <rect x="4" y="10" width="40" height="28" rx="4" />
      <circle cx="16" cy="21" r="4" />
      <path d="M9 32c0-4 3-6 7-6s7 2 7 6M28 19h10M28 25h10M28 31h6" />
    </>
  ),
  document: (
    <>
      <path d="M12 4h17l9 9v31H12z" />
      <path d="M29 4v9h9M18 22h14M18 29h14M18 36h9" />
    </>
  ),
  certificate: (
    <>
      <rect x="5" y="7" width="38" height="27" rx="2" />
      <path d="M11 15h26M11 21h18" />
      <circle cx="34" cy="33" r="5" className="fill-soft" />
      <path d="M31 37l-2 7 5-2 5 2-2-7" />
    </>
  ),
  rings: (
    <>
      <circle cx="18" cy="29" r="10" />
      <circle cx="30" cy="29" r="10" />
      <path d="M14 13l4-5 4 5-4 4z" />
    </>
  ),
  bank: (
    <>
      <path d="M4 18L24 6l20 12z" />
      <path d="M11 22v13M19 22v13M29 22v13M37 22v13M6 36h36M4 42h40" />
    </>
  ),
  calendar: (
    <>
      <rect x="6" y="10" width="36" height="32" rx="3" />
      <path d="M6 19h36M16 6v8M32 6v8" />
      <path d="M14 27h4M22 27h4M30 27h4M14 34h4M22 34h4" />
    </>
  ),
  rules: (
    <>
      <path d="M24 12c-5-4-12-4-18-3v30c6-1 13-1 18 3 5-4 12-4 18-3V9c-6-1-13-1-18 3z" />
      <path d="M24 12v30" />
    </>
  ),
  'cloud-off': (
    <>
      <path d="M14 36h21a8 8 0 0 0 1-16 11 11 0 0 0-21-2 9 9 0 0 0-1 18z" />
      <path d="M8 8l32 32" />
    </>
  ),
  heart: <path d="M24 41S6 30 6 17a9 9 0 0 1 18-3 9 9 0 0 1 18 3c0 13-18 24-18 24z" />,
  briefcase: (
    <>
      <rect x="6" y="16" width="36" height="24" rx="3" />
      <path d="M18 16v-5h12v5M6 26h36" />
    </>
  ),
  gear: (
    <>
      <circle cx="24" cy="24" r="6" />
      <circle cx="24" cy="24" r="12" />
      <path d="M36 24h5M24 36v5M12 24H7M24 12V7M32.5 32.5l3.5 3.5M15.5 32.5L12 36M15.5 15.5L12 12M32.5 15.5L36 12" />
    </>
  ),
  search: (
    <>
      <circle cx="20" cy="20" r="12" />
      <path d="M29 29l13 13" />
    </>
  ),
  speaker: (
    <>
      <path d="M8 19h7l10-8v26l-10-8H8z" className="fill" />
      <path d="M31 18a8 8 0 0 1 0 12M36 13a15 15 0 0 1 0 22" />
    </>
  ),
  'arrow-left': <path d="M40 24H9M20 13L9 24l11 11" />,
  'arrow-right': <path d="M8 24h31M28 13l11 11-11 11" />,
  plus: <path d="M24 8v32M8 24h32" />,
} satisfies Record<string, ReactElement>

export type IconName = keyof typeof SHAPES

// A small amber badge in the corner for "needs a second look". Never red, never a verdict.
export type IconBadge = '?' | '!'

interface IconProps {
  name: IconName
  size?: number
  // Spoken name for screen readers. Leave it out when the icon sits next to its own text.
  label?: string
  badge?: IconBadge
  className?: string
}

export function Icon({ name, size = 40, label, badge, className }: IconProps) {
  const a11y = label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': true }
  return (
    <svg
      className={`pictogram ${className ?? ''}`}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      focusable="false"
      {...a11y}
    >
      {SHAPES[name]}
      {badge && (
        <g className="badge">
          <circle cx="38" cy="38" r="9" />
          <text x="38" y="42.5" textAnchor="middle">{badge}</text>
        </g>
      )}
    </svg>
  )
}
