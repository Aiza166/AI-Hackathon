import { Fragment, useEffect, useState } from 'react'
import { api, errorText, getToken } from '../api/client'
import { Icon } from '../lib/icons'
import { Badge, ErrorNote, Loading, humanize } from './ui'

// Officer view of uploaded papers: every indicator with its evidence and "what this cannot
// tell", the registry checks, the stored photo with marked regions, and the ELA heatmap.
// Indicators say "needs a second look"; they are never a verdict.

const BASE: string = import.meta.env.VITE_API_BASE ?? ''

interface Indicator {
  code: string
  severity: 'high' | 'mismatch' | 'confirm' | 'info'
  text_en: string
  cannot_tell_en: string
  evidence: Record<string, unknown>
}

interface Check {
  field: string
  status: string
  read_value: string | null
  record_value: string | null
  note: string
}

interface OfficerDoc {
  id: string
  kind: string
  width: number
  height: number
  risk_level: string
  indicators: Indicator[]
  checks: Check[]
  fields: Record<string, { value: string; confidence: number; method: string }>
  corrected_fields: string[]
  forensics: { copy_move?: { regions?: number[][]; score?: number }; ela_mean?: number; exif?: Record<string, string> }
  jev: { status?: string; model?: string | null; answers?: Record<string, { p: number; band: string }>; boxes?: Record<string, number[]> }
  ocr_engine: string | null
  created_at: string
}

const TONE: Record<string, 'risk' | 'attn' | 'info' | 'quiet'> = { high: 'risk', mismatch: 'attn', confirm: 'info', info: 'quiet', low: 'quiet' }

function useAuthImage(path: string): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    let objectUrl: string | null = null
    const token = getToken()
    fetch(`${BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((r) => (r.ok ? r.blob() : null))
      .then((blob) => {
        if (!active || !blob) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => undefined)
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [path])
  return url
}

export function DocumentReview({ caseId }: { caseId: string }) {
  const [docs, setDocs] = useState<OfficerDoc[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api<OfficerDoc[]>(`/api/v1/cases/${caseId}/documents`)
      .then((r) => active && setDocs(r.data))
      .catch((e: unknown) => active && setError(errorText(e)))
    return () => {
      active = false
    }
  }, [caseId])

  if (error) return <ErrorNote message={error} />
  if (!docs) return <Loading label="Loading documents" />
  if (docs.length === 0) return <p className="muted">No document photos uploaded for this case.</p>
  return (
    <section className="stack" aria-label="Uploaded documents">
      <h3 className="detail-sub">Documents</h3>
      {docs.map((d) => <DocCard key={d.id} caseId={caseId} doc={d} />)}
    </section>
  )
}

function DocCard({ caseId, doc }: { caseId: string; doc: OfficerDoc }) {
  const image = useAuthImage(`/api/v1/cases/${caseId}/documents/${doc.id}/image`)
  const ela = useAuthImage(`/api/v1/cases/${caseId}/documents/${doc.id}/ela`)
  const regions = doc.forensics.copy_move?.regions ?? []
  const boxes = Object.entries(doc.jev.boxes ?? {})
  return (
    <article className="doc-review">
      <header className="detail-head">
        <strong>{humanize(doc.kind)}</strong>
        <Badge tone={TONE[doc.risk_level] ?? 'quiet'}>{doc.risk_level === 'high' ? 'Needs a second look' : humanize(doc.risk_level)}</Badge>
      </header>
      {doc.indicators.length === 0 && <p className="muted">No indicators. Read by {doc.ocr_engine ?? 'nobody (OCR unavailable)'}.</p>}
      <ul className="doc-indicators">
        {doc.indicators.map((i) => (
          <li key={i.code} className={`doc-ind sev-${i.severity}`}>
            <span className="doc-ind-head"><code className="code">{i.code}</code> <span>{i.text_en}</span></span>
            <span className="fine">Cannot tell: {i.cannot_tell_en}</span>
          </li>
        ))}
      </ul>
      {doc.checks.length > 0 && (
        <table className="table table-dense">
          <thead><tr><th scope="col">Field</th><th scope="col">On paper</th><th scope="col">Record</th><th scope="col">Result</th></tr></thead>
          <tbody>
            {doc.checks.map((c) => (
              <tr key={c.field} className={c.status === 'mismatch' ? 'is-flagged' : undefined}>
                <td>{humanize(c.field)}{doc.corrected_fields.includes(c.field) && <span className="fine"> (typed by citizen)</span>}</td>
                <td>{c.read_value ?? '-'}</td>
                <td>{c.record_value ?? '-'}</td>
                <td title={c.note}>{humanize(c.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="doc-images">
        <figure className="doc-figure">
          <div className="doc-frame">
            {image ? <img src={image} alt={`${humanize(doc.kind)} as uploaded`} /> : <Loading label="Loading photo" />}
            {regions.map((r, idx) => (
              <span key={`r${idx}`} className="doc-mark" style={{ left: `${(r[0] / doc.width) * 100}%`, top: `${(r[1] / doc.height) * 100}%`,
                width: `${((r[2] - r[0]) / doc.width) * 100}%`, height: `${((r[3] - r[1]) / doc.height) * 100}%` }} />
            ))}
            {boxes.map(([name, b]) => (
              <span key={name} className="doc-mark doc-mark-jev" title={humanize(name)} style={{ left: `${b[0] * 100}%`, top: `${b[1] * 100}%`,
                width: `${(b[2] - b[0]) * 100}%`, height: `${(b[3] - b[1]) * 100}%` }} />
            ))}
          </div>
          <figcaption className="fine">Red: near-identical stamps. Blue: where the AI sensor pointed.</figcaption>
        </figure>
        <figure className="doc-figure">
          <div className="doc-frame">{ela ? <img src={ela} alt="Error level analysis heatmap" /> : <Loading label="Loading heatmap" />}</div>
          <figcaption className="fine">ELA heatmap: context only. Recompression and screenshots change it too.</figcaption>
        </figure>
      </div>
      <details>
        <summary><Icon name="eye" size={16} /> Fields read and sensor answers</summary>
        <dl className="facts">
          {Object.entries(doc.fields).map(([k, f]) => (
            <Fragment key={k}><dt>{humanize(k)}</dt><dd>{f.value} <span className="muted">({Math.round(f.confidence * 100)}%, {f.method})</span></dd></Fragment>
          ))}
          <dt>Jev</dt>
          <dd>{doc.jev.status === 'ok'
            ? `${doc.jev.model}: ${Object.entries(doc.jev.answers ?? {}).map(([k, a]) => `${k} ${a.p.toFixed(2)} (${a.band})`).join(', ')}`
            : humanize(doc.jev.status ?? 'skipped')}</dd>
          {doc.forensics.exif && Object.keys(doc.forensics.exif).length > 0 && (
            <><dt>Photo metadata</dt><dd>{Object.entries(doc.forensics.exif).map(([k, v]) => `${k}: ${v}`).join('; ')} (context only)</dd></>
          )}
        </dl>
      </details>
    </article>
  )
}
