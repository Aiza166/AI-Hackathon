import { useState } from 'react'
import { errorText, post } from '../api/client'
import type { ReportRoute, ScamResult, ScamVerdict } from '../api/types'
import { Badge, Bilingual, ErrorNote, ListenButton, Pictogram } from '../components/ui'
import { Icon } from '../lib/icons'

// Scam Shield: "is this pension message a scam?" for citizens and helpers.
// The verdict and reasons come from the server (fixed text); this screen only shows them.

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
// Mock districts (match the seeded demo world) so the staff Scam Map can group reports.
const AREAS = ['Karachi East', 'Karachi South', 'Hyderabad', 'Sukkur', 'Multan', 'Lahore', 'Faisalabad', 'Quetta']
const DEMO_SCAM = 'Mubarak ho! Aap ki pension release ho gayi hai. Rs 5000 processing fee aaj hi jama karwain warna cancel. Link: pension-release.example.com'
const INTRO_UR = 'جو پیغام آیا ہے وہ یہاں لکھیں یا چسپاں کریں۔ ہم بتائیں گے کہ یہ دھوکہ تو نہیں۔'
const ON_CALL_UR = 'کیا اس وقت کوئی فون پر آپ کو یہ کرنے کو کہہ رہا ہے؟'

interface ScamShieldProps {
  onBack: () => void
}

export function ScamShield({ onBack }: ScamShieldProps) {
  const [text, setText] = useState('')
  const [sender, setSender] = useState('')
  const [onCall, setOnCall] = useState<boolean | null>(null)
  const [area, setArea] = useState('')
  const [result, setResult] = useState<ScamResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function check(): Promise<void> {
    setBusy(true)
    setError(null)
    try {
      const body = { text: text.trim(), sender: sender.trim() || null, on_call_with_unknown: onCall, area: area || null }
      setResult((await post<ScamResult>('/api/v1/scam/check', body)).data)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  function startAgain(): void {
    setResult(null)
    setText('')
    setSender('')
    setOnCall(null)
  }

  return (
    <section className="stack-lg" aria-labelledby="scam-title">
      <button type="button" className="btn btn-ghost btn-sm self-start" onClick={onBack}>
        <Icon name="arrow-left" size={20} />
        <span lang="ur" dir="rtl">واپس</span>
        <span>Back</span>
      </button>
      <div className="hello">
        <Bilingual as="h1" id="scam-title" ur="کیا یہ پیغام دھوکہ ہے؟" en="Scam Shield: is this message a scam?" />
        <ListenButton audioKey="prompt_scam_intro" text={INTRO_UR} />
      </div>

      {!result && (
        <form className="form" onSubmit={(e) => { e.preventDefault(); void check() }}>
          <label className="field">
            <span className="field-label">
              <Icon name="phone" size={22} />
              <span lang="ur" dir="rtl">پیغام یہاں لکھیں یا چسپاں کریں</span>
              <span>Paste or type the message</span>
            </span>
            <textarea className="input" rows={5} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} required />
          </label>
          <button type="button" className="btn btn-quiet btn-sm self-start" onClick={() => setText(DEMO_SCAM)}>Fill demo scam SMS (mock)</button>

          <label className="field">
            <span className="field-label">
              <span lang="ur" dir="rtl">کس نمبر سے آیا؟ (اختیاری)</span>
              <span>Sender number or name (optional)</span>
            </span>
            <span dir="ltr" className="ltr-island">
              <input className="input input-big input-digits" maxLength={40} autoComplete="off" value={sender} onChange={(e) => setSender(e.target.value)} />
            </span>
          </label>

          <fieldset className="fieldset">
            <legend className="field-label">
              <span lang="ur" dir="rtl">{ON_CALL_UR}</span>
              <span>Is someone on the phone telling you to do this right now?</span>
            </legend>
            <div className="choice-grid choice-2">
              <button type="button" className="choice" aria-pressed={onCall === true} onClick={() => setOnCall(true)}>
                <Icon name="phone" size={40} />
                <span lang="ur" dir="rtl" className="choice-ur">ہاں</span>
                <span className="choice-en">Yes</span>
                {onCall === true && <span className="choice-tick"><Icon name="check" size={22} /></span>}
              </button>
              <button type="button" className="choice" aria-pressed={onCall === false} onClick={() => setOnCall(false)}>
                <Icon name="close" size={40} />
                <span lang="ur" dir="rtl" className="choice-ur">نہیں</span>
                <span className="choice-en">No</span>
                {onCall === false && <span className="choice-tick"><Icon name="check" size={22} /></span>}
              </button>
            </div>
          </fieldset>

          <label className="field">
            <span className="field-label">
              <span lang="ur" dir="rtl">آپ کا ضلع (اختیاری)</span>
              <span>Your district (optional, helps warn others)</span>
            </span>
            <select className="input input-big" value={area} onChange={(e) => setArea(e.target.value)}>
              <option value="">Not saying</option>
              {AREAS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </label>

          <ErrorNote message={error} />
          <button type="submit" className="btn btn-primary btn-big" disabled={busy || text.trim().length === 0}>
            <Icon name="shield" size={24} />
            <span lang="ur" dir="rtl">جانچ کریں</span>
            <span className="btn-en">{busy ? 'Checking…' : 'Check this message'}</span>
          </button>
          <p className="fine">We keep only a fingerprint of the message, not the text or the number.</p>
        </form>
      )}

      {result && <ScamVerdictView result={result} onAgain={startAgain} />}
    </section>
  )
}

function ScamVerdictView({ result, onAgain }: { result: ScamResult; onAgain: () => void }) {
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
            <span lang="ur" dir="rtl" className="note-ur">آپ کے دعوے میں کوئی ادائیگی باقی نہیں۔</span>
            Checked against your claim: {result.case_cross_check}
          </span>
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

const KIND_ICON: Record<ReportRoute['kind'], string> = { call: 'phone', link: 'arrow-right', sms: 'phone', info: 'bank' }

function ReportCard({ routes }: { routes: ReportRoute[] }) {
  return (
    <section className="report-card" aria-labelledby="report-title">
      <Bilingual as="h3" id="report-title" ur="اس دھوکے کی شکایت کریں" en="Report this scam" />
      <p className="fine">Real Pakistani help lines (not part of this prototype). Source and status shown for each.</p>
      <ul className="route-list">
        {routes.map((r) => (
          <li key={r.id} className="route-item">
            {r.url ? (
              <a
                className="route-action"
                href={r.url}
                {...(r.kind === 'link' ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
              >
                <Icon name={KIND_ICON[r.kind]} size={24} />
                <span className="bi">
                  <span className="bi-ur" lang="ur" dir="rtl">{r.name_ur}</span>
                  <span className="bi-en">{r.name}</span>
                </span>
              </a>
            ) : (
              <span className="route-action route-info">
                <Icon name={KIND_ICON[r.kind]} size={24} />
                <span className="bi">
                  <span className="bi-ur" lang="ur" dir="rtl">{r.name_ur}</span>
                  <span className="bi-en">{r.name}</span>
                </span>
              </span>
            )}
            <span className="route-meta">
              <Badge tone={r.confidence === 'confirmed' ? 'ok' : 'quiet'}>{r.confidence}</Badge>
              {r.source && (
                <a className="fine" href={r.source} target="_blank" rel="noopener noreferrer">source</a>
              )}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
