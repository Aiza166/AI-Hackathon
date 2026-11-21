import { useEffect, useState } from 'react'
import { api, errorText } from '../api/client'
import type { ScamMapData } from '../api/types'
import { Badge, ErrorNote, Loading, humanize } from '../components/ui'

// Scam Map for staff: where and when scam messages are being checked.
// Counts only: the server never stores message text or phone numbers.

const RANGES = [7, 30, 90] as const

export function ScamMap() {
  const [days, setDays] = useState<number>(7)
  const [data, setData] = useState<ScamMapData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api<ScamMapData>(`/api/v1/scam/map?days=${days}`)
      .then((r) => { if (active) { setData(r.data); setError(null) } })
      .catch((e: unknown) => { if (active) setError(errorText(e)) })
    return () => { active = false }
  }, [days])

  const scams = data?.by_verdict.LIKELY_SCAM ?? 0
  return (
    <section className="stack-lg" aria-labelledby="map-title">
      <div className="page-head">
        <h1 id="map-title" className="page-title">Scam Map</h1>
        <div className="row" role="group" aria-label="Time range">
          {RANGES.map((d) => (
            <button key={d} type="button" className={d === days ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'} aria-pressed={d === days} onClick={() => setDays(d)}>
              {d} days
            </button>
          ))}
        </div>
      </div>
      <p className="page-sub">Messages checked with Scam Shield in your department. Counts only: no message text, no phone numbers.</p>
      <ErrorNote message={error} />
      {!data && !error && <Loading label="Loading scam map" />}
      {data && (
        <>
          <div className="stat-row">
            <Stat label="Messages checked" value={data.total_checked} />
            <Stat label="Likely scam" value={scams} tone="risk" />
            <Stat label="Not sure" value={data.by_verdict.NOT_SURE ?? 0} tone="attn" />
            <Stat label="Looks genuine" value={data.by_verdict.LOOKS_GENUINE ?? 0} tone="ok" />
          </div>
          <div className="map-grid">
            <Bars title="Scams by district" counts={data.scams_by_area} />
            <Bars title="Scams by type" counts={data.scams_by_type} />
            <HourStrip counts={data.scams_by_hour} />
          </div>
        </>
      )}
    </section>
  )
}

function Stat({ label, value, tone = 'info' }: { label: string; value: number; tone?: 'info' | 'risk' | 'attn' | 'ok' }) {
  return (
    <div className={`stat tone-${tone}`}>
      <span className="stat-n">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}

function Bars({ title, counts }: { title: string; counts: Record<string, number> }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...entries.map(([, n]) => n))
  return (
    <section className="detail" aria-label={title}>
      <h2 className="h-plain">{title}</h2>
      {entries.length === 0 && <p className="muted">No scams reported in this period.</p>}
      <ul className="bars">
        {entries.map(([k, n]) => (
          <li key={k} className="bar-row">
            <span className="bar-label">{humanize(k)}</span>
            <span className="bar-track" aria-hidden="true"><span className="bar-fill" style={{ width: `${(n / max) * 100}%` }} /></span>
            <Badge tone="risk">{n}</Badge>
          </li>
        ))}
      </ul>
    </section>
  )
}

function HourStrip({ counts }: { counts: Record<string, number> }) {
  const max = Math.max(1, ...Object.values(counts))
  const hours = Array.from({ length: 24 }, (_, h) => ({ h, n: counts[String(h)] ?? 0 }))
  return (
    <section className="detail" aria-label="Scams by hour (UTC)">
      <h2 className="h-plain">Scams by hour (UTC)</h2>
      <div className="hours">
        {hours.map(({ h, n }) => (
          <span key={h} className="hour" title={`${h}:00 - ${n}`} aria-label={`${h}:00, ${n} scams`}>
            <span className="hour-fill" style={{ height: `${(n / max) * 100}%` }} />
          </span>
        ))}
      </div>
      <div className="hours-axis fine"><span>0</span><span>6</span><span>12</span><span>18</span><span>23</span></div>
    </section>
  )
}
