import type { ReportRoute, ScamLink, ScamResult, ScamVerdict } from '../api/types'
import { Badge, Bilingual, ListenButton, Pictogram } from './ui'
import { Icon } from '../lib/icons'

// Scam Shield result: the verdict and reasons come from the server (fixed text); this only shows them.

const VERDICT: Record<ScamVerdict, { icon: string; tone: 'risk' | 'attn' | 'ok'; ur: string; en: string }> = {
  LIKELY_SCAM: {
    icon: 'warning', tone: 'risk',
    ur: 'یہ دھوکہ لگتا ہے۔ پیسے یا کوڈ ہرگز نہ دیں۔',
    en: 'This looks like a scam. Do not send money or share a code.',
  },
  NOT_SURE: {
    icon: 'question', tone: 'attn',
    ur: 'ہمیں یقین نہیں۔ کچھ کرنے سے پہلے مددگار یا افسر سے پوچھیں۔',
    en: 'We are not sure. Ask a helper or an officer before you do anything.',
  },
  LOOKS_GENUINE: {
    icon: 'check', tone: 'ok',
    ur: 'یہ پیغام ٹھیک لگتا ہے۔ پھر بھی کبھی فیس یا کوڈ نہ دیں۔',
    en: 'This message looks genuine. Still, never pay a fee or share a code.',
  },
}

interface ScamVerdictViewProps {
  result: ScamResult
  onAgain: () => void
}

export function ScamVerdictView({ result, onAgain }: ScamVerdictViewProps) {
  const v = VERDICT[result.verdict]
  const spoken = [v.ur, ...result.reasons_ur].join(' ')
  return (
    <div className="stack-lg">
      <div className={`verdict tone-${v.tone}`} role="status" aria-live="polite">
        <Pictogram name={v.icon} tone={v.tone} size="lg" />
        <Bilingual as="h2" ur={v.ur} en={v.en} />
        <ListenButton audioKey={`scam_${result.verdict.toLowerCase()}`} text={spoken} />
      </div>

      {result.reasons.length > 0 && (
        <section className="stack" aria-labelledby="scam-reasons">
          <Bilingual as="h3" id="scam-reasons" ur="کیوں؟" en="Why" />
          <ul className="reason-list">
            {result.reasons.map((en, i) => (
              <li key={en} className="reason-item">
                <Icon name="warning" size={22} />
                <span className="bi">
                  {result.reasons_ur[i] && <span className="bi-ur" lang="ur" dir="rtl">{result.reasons_ur[i]}</span>}
                  <span className="bi-en">{en}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.case_cross_check && (
        <p className="note note-info">
          <Icon name="document" size={20} />
          <span>
            {result.case_cross_check_ur && <span lang="ur" dir="rtl" className="note-ur">{result.case_cross_check_ur}</span>}
            Checked against your claim: {result.case_cross_check}
          </span>
        </p>
      )}

      {result.links && result.links.length > 0 && <LinkList links={result.links} />}
      {result.extracted && <Extracted text={result.extracted.text} />}
      {result.officer_note && (
        <p className="note note-info">
          <Badge tone="quiet">AI-written, advisory (staff only)</Badge> {result.officer_note.replace(/^AI-written, advisory:\s*/, '')}
        </p>
      )}

      {result.verdict === 'LIKELY_SCAM' && result.report_routes.length > 0 && <ReportCard routes={result.report_routes} />}

      <button type="button" className="btn btn-secondary btn-big" onClick={onAgain}>
        <span lang="ur" dir="rtl">دوسرا پیغام جانچیں</span>
        <span className="btn-en">Check another message</span>
      </button>
    </div>
  )
}

function LinkList({ links }: { links: ScamLink[] }) {
  return (
    <section className="stack" aria-labelledby="scam-links">
      <Bilingual as="h3" id="scam-links" ur="لنک جو ہم نے جانچے (کھولے نہیں)" en="Links we checked (never opened)" />
      <ul className="reason-list">
        {links.map((l, i) => (
          <li key={`${l.host}-${i}`} className="reason-item">
            <Icon name="link" size={22} />
            <span className="bi">
              <span className="bi-en ltr-island" dir="ltr">{l.host}</span>
              <span className="fine">
                {l.official ? `official (${l.official_label})` : l.imitates ? `copies ${l.imitates}` : 'not an official website'}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Extracted({ text }: { text: string }) {
  return (
    <details className="stack">
      <summary>
        <span lang="ur" dir="rtl">ہم نے کیا پڑھا یا سنا</span> What we read or heard
      </summary>
      <p className="fine" dir="auto" style={{ whiteSpace: 'pre-wrap' }}>{text}</p>
    </details>
  )
}

const KIND_ICON: Record<ReportRoute['kind'], string> = { call: 'phone', link: 'arrow-right', sms: 'message', info: 'bank' }

function ReportCard({ routes }: { routes: ReportRoute[] }) {
  return (
    <section className="report-card" aria-labelledby="report-title">
      <Bilingual as="h3" id="report-title" ur="اس دھوکے کی شکایت کریں" en="Report this scam" />
      <p className="fine">Real Pakistani help lines (not part of this prototype). Source and status shown for each.</p>
      <ul className="route-list">
        {routes.map((r) => (
          <li key={r.id} className="route-item">
            {r.url ? (
              <a className="route-action" href={r.url} {...(r.kind === 'link' ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>
                <RouteLabel route={r} />
              </a>
            ) : (
              <span className="route-action route-info"><RouteLabel route={r} /></span>
            )}
            <span className="route-meta">
              <Badge tone={r.confidence === 'confirmed' ? 'ok' : 'quiet'}>{r.confidence}</Badge>
              {r.source && <a className="fine" href={r.source} target="_blank" rel="noopener noreferrer">source</a>}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function RouteLabel({ route }: { route: ReportRoute }) {
  return (
    <>
      <Icon name={KIND_ICON[route.kind]} size={24} />
      <span className="bi">
        <span className="bi-ur" lang="ur" dir="rtl">{route.name_ur}</span>
        <span className="bi-en">{route.name}</span>
      </span>
    </>
  )
}
