import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, SESSION_ENDED_EVENT, api, apiUrl, errorText, getToken, post } from '../api/client'
import { Badge, ErrorNote, formatTime } from '../components/ui'
import { Icon } from '../lib/icons'
import './staff-console.css'

// Judge console (platform admin only; the server enforces it on every call and audits every change).
// One screen to run the demo and let judges break it: mock-service faults, simulated AI outages,
// live status, demo shortcuts and the last 20 audit events.

type FaultMode = 'ok' | 'timeout' | 'error' | 'slow'
type OutageTarget = 'jev' | 'second_sensor' | 'azure_ocr' | 'azure_speech'
type ConsoleStatus = {
  readiness: { database: string; jev_reachable: boolean; jev_model: string; jev_simulated_down: boolean }
  providers: Record<'jev' | 'second_sensor' | 'azure_ocr' | 'azure_speech' | 'tesseract' | 'ffmpeg', boolean> & {
    jev_model: string; second_sensor_model: string | null
  }
  faults: Record<string, FaultMode>
  outages: Record<OutageTarget, { simulated_down: boolean; expires_at: string | null }>
  outage_minutes: number
  last_eval: { generated_at: string | null; source: string; scam_mode: string | null } | null
  audit_chain: { intact: boolean; checked: number; first_broken_seq: number | null }
}
type ActivityRow = { seq: number; ts: string; actor_type: string; role: string | null; action: string; reason: string | null }
type SampleDoc = { file: string; doc: string; variant: string; edited: boolean }

const SERVICES: { key: string; label: string; effect: string }[] = [
  { key: 'identity', label: 'NADRA identity', effect: 'New claims go to an officer (SERVICE_UNAVAILABLE), never a guess.' },
  { key: 'frc', label: 'NADRA family record (FRC)', effect: 'Family check cannot run: claim goes to an officer.' },
  { key: 'death_registry', label: 'Death registry', effect: 'Death cannot be confirmed: claim goes to an officer.' },
  { key: 'pension_office', label: 'Pension office', effect: 'Pension record unavailable: claim goes to an officer.' },
  { key: 'raast', label: 'Raast title fetch', effect: 'Claim UNSURE; payout change flagged, held 4 business days.' },
]
const MODES: FaultMode[] = ['ok', 'timeout', 'error', 'slow']
const SLOW_MS = 1500 // slow but still answering (2 s or more counts as down on the server)

const OUTAGES: { key: OutageTarget; label: string; fallback: string }[] = [
  { key: 'jev', label: 'Jev (jev-1.14.0)', fallback: 'Scam Shield uses keyword + link rules and never says "looks genuine"; documents keep copy-move + registry checks.' },
  { key: 'second_sensor', label: 'Second sensor (gpt-5-mini)', fallback: 'Cascade runs Jev + deterministic checks; conflicts stay "unresolved".' },
  { key: 'azure_ocr', label: 'Azure OCR', fallback: 'Documents and screenshots fall back to Tesseract (or "an officer will read it").' },
  { key: 'azure_speech', label: 'Azure speech (TTS/STT)', fallback: 'The app speaks with the phone\'s own voice; voice notes ask her to type.' },
]

const PERSONAS: { name: string; phone: string; note: string }[] = [
  { name: 'Zainab Bibi', phone: '00000000001', note: 'Widow, golden path (name variants)' },
  { name: 'Rukhsana', phone: '00000000002', note: 'Competing claimant (red flag)' },
  { name: 'Bilal Haider', phone: '00000000005', note: 'Heir: sees "paid until 2034-11-01" after v2' },
  { name: 'Rafiq', phone: '00000000007', note: 'Shopkeeper with scam messages' },
  { name: 'Ayesha', phone: '00000000010', note: 'Community helper, 40 families' },
  { name: 'Kamran', phone: '00000000020', note: 'Pension officer, review queue' },
  { name: 'Admin', phone: '00000000030', note: 'Rules, Digital Twin, this console' },
  { name: 'Auditor', phone: '00000000040', note: 'Read-only audit log and replay' },
]

const SCAM_SAMPLES: { label: string; expect: string; text: string; sender: string }[] = [
  { label: 'Fee scam (SMS)', expect: 'LIKELY_SCAM', sender: '0300-0000000', text: 'Your pension is released! Pay Rs 5000 processing fee today at pension-release.example.com or it will be cancelled.' },
  { label: 'Look-alike link', expect: 'LIKELY_SCAM', sender: '0300-0000019', text: 'BISP: your Rs 25,000 instalment is ready. Verify your CNIC at https://bisp-gov.pk.verify-cnic.top/login today.' },
  { label: 'Spoofed 8171 caller asks for a code', expect: 'LIKELY_SCAM', sender: '8171', text: 'Caller: I am calling from BISP 8171. A code has come on your phone. Tell me the code so we can release your money.' },
  { label: 'Borderline: "call this number"', expect: 'NOT_SURE', sender: '0300-0000002', text: 'Your pension has been released. Call 0300-0000002 now to receive it before it expires.' },
  { label: 'Genuine notice', expect: 'LOOKS_GENUINE', sender: 'PENSION-GOV', text: 'Your claim SP-1042 has been received. An officer will review it within 7 working days.' },
]

export function JudgeConsole({ onOpenRules }: { onOpenRules: () => void }) {
  const [status, setStatus] = useState<ConsoleStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const loadStatus = useCallback(async () => {
    try {
      setStatus((await api<ConsoleStatus>('/api/v1/admin/judge/status')).data)
      setError(null)
    } catch (e) {
      setError(errorText(e))
    }
  }, [])

  useEffect(() => {
    void loadStatus()
  }, [loadStatus])

  return (
    <div className="stack-lg">
      <div className="demo-banner" role="note">
        <Icon name="warning" size={24} />
        <div>
          <strong>PROTOTYPE / DEMO CONTROLS</strong>
          <p className="muted">Mock services and test switches only. Every action here is checked on the server (admin only) and written to the audit log.</p>
        </div>
      </div>
      <ErrorNote message={error} />
      <div role="status" aria-live="polite">
        {notice && <p className="note note-ok"><Icon name="check" size={20} /><span>{notice}</span></p>}
      </div>
      <div className="console-grid">
        <StatusPanel status={status} onRefresh={() => void loadStatus()} />
        <FaultPanel status={status} onChanged={loadStatus} onNotice={setNotice} onError={setError} />
        <OutagePanel status={status} onChanged={loadStatus} onNotice={setNotice} onError={setError} />
        <ShortcutsPanel onOpenRules={onOpenRules} onNotice={setNotice} onError={setError} />
        <ScamSamples />
        <SampleDocs onError={setError} />
      </div>
      <ActivityFeed />
    </div>
  )
}

function YesNo({ ok, yes = 'Yes', no = 'No' }: { ok: boolean; yes?: string; no?: string }) {
  return <Badge tone={ok ? 'ok' : 'risk'}>{ok ? <><Icon name="check" size={14} /> {yes}</> : <><Icon name="close" size={14} /> {no}</>}</Badge>
}

function StatusPanel({ status, onRefresh }: { status: ConsoleStatus | null; onRefresh: () => void }) {
  return (
    <section className="eval-section" aria-labelledby="status-title">
      <div className="eval-head">
        <h2 id="status-title">Live status</h2>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRefresh}>Refresh</button>
      </div>
      {!status ? <p className="loading" role="status">Loading status…</p> : (
        <dl className="status-list">
          <dt>Database</dt><dd><YesNo ok={status.readiness.database === 'ok'} yes="OK" no="Down" /></dd>
          <dt>Jev reachable</dt>
          <dd>
            <YesNo ok={status.readiness.jev_reachable} />
            <code className="code">{status.readiness.jev_model}</code>
            {status.readiness.jev_simulated_down && <Badge tone="attn">simulated outage</Badge>}
          </dd>
          <dt>Second sensor configured</dt>
          <dd><YesNo ok={status.providers.second_sensor} />{status.providers.second_sensor_model && <code className="code">{status.providers.second_sensor_model}</code>}</dd>
          <dt>Azure OCR configured</dt><dd><YesNo ok={status.providers.azure_ocr} /></dd>
          <dt>Azure speech configured</dt><dd><YesNo ok={status.providers.azure_speech} /></dd>
          <dt>Tesseract / ffmpeg (fallbacks)</dt><dd><YesNo ok={status.providers.tesseract} /> <YesNo ok={status.providers.ffmpeg} /></dd>
          <dt>Last evaluation</dt>
          <dd>{status.last_eval?.generated_at ? `${formatTime(status.last_eval.generated_at)} (${status.last_eval.source.replace('_', ' ')}, scam ${status.last_eval.scam_mode})` : 'none yet'}</dd>
          <dt>Audit chain</dt>
          <dd>
            <YesNo ok={status.audit_chain.intact} yes="Intact" no={`Broken at #${status.audit_chain.first_broken_seq}`} />
            <span className="muted">{status.audit_chain.checked} events checked</span>
          </dd>
        </dl>
      )}
      <p className="muted">Keys are never shown: only whether each provider is set up.</p>
    </section>
  )
}

interface ActionPanelProps {
  status: ConsoleStatus | null
  onChanged: () => Promise<void>
  onNotice: (text: string | null) => void
  onError: (text: string | null) => void
}

function FaultPanel({ status, onChanged, onNotice, onError }: ActionPanelProps) {
  const [busy, setBusy] = useState<string | null>(null)

  async function setMode(service: string, mode: FaultMode): Promise<void> {
    if (busy !== null || !status || status.faults[service] === mode) return
    setBusy(service)
    onError(null)
    try {
      await post('/api/v1/admin/faults', { service, mode, latency_ms: mode === 'slow' ? SLOW_MS : 0 })
      onNotice(`${SERVICES.find((s) => s.key === service)?.label ?? service}: ${mode}. File a claim to see the effect.`)
      await onChanged()
    } catch (e) {
      onError(errorText(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="eval-section" aria-labelledby="faults-title">
      <h2 id="faults-title">Break a mock government service</h2>
      <p className="muted">"Slow" waits {SLOW_MS / 1000} s and still answers. Timeout and error make the service unavailable.</p>
      <ul className="svc-list">
        {SERVICES.map((s) => {
          const mode = status?.faults[s.key] ?? 'ok'
          return (
            <li key={s.key} className={mode === 'ok' ? 'svc' : 'svc is-broken'}>
              <span className="svc-name">{s.label}<small id={`fx-${s.key}`}>{s.effect}</small></span>
              <div className="seg" role="group" aria-label={`${s.label} mode`} aria-describedby={`fx-${s.key}`} aria-busy={busy === s.key}>
                {MODES.map((m) => (
                  <button key={m} type="button" className="seg-btn" aria-pressed={mode === m} onClick={() => void setMode(s.key, m)}>
                    {m}
                  </button>
                ))}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function minutesLeft(iso: string | null, now: number): number | null {
  if (!iso) return null
  return Math.max(0, Math.ceil((new Date(iso).getTime() - now) / 60000))
}

function OutagePanel({ status, onChanged, onNotice, onError }: ActionPanelProps) {
  const [busy, setBusy] = useState<OutageTarget | null>(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30000)
    return () => window.clearInterval(id)
  }, [])

  async function toggle(target: OutageTarget, down: boolean): Promise<void> {
    setBusy(target)
    onError(null)
    try {
      await post('/api/v1/admin/judge/outages', { target, down })
      const label = OUTAGES.find((o) => o.key === target)?.label ?? target
      onNotice(down ? `${label} now behaves as if it were down (switches itself off after ${status?.outage_minutes ?? 15} minutes).` : `${label} restored.`)
      await onChanged()
    } catch (e) {
      onError(errorText(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="eval-section" aria-labelledby="outages-title">
      <h2 id="outages-title">Simulate an AI provider outage</h2>
      <p className="muted">Shows the fallback live. Each switch turns itself off after {status?.outage_minutes ?? 15} minutes and on demo reset.</p>
      <ul className="svc-list">
        {OUTAGES.map((o) => {
          const state = status?.outages[o.key]
          const down = !!state?.simulated_down
          const left = minutesLeft(state?.expires_at ?? null, now)
          return (
            <li key={o.key} className={down ? 'svc is-broken' : 'svc'}>
              <span className="svc-name">
                {o.label}
                <small>{down ? `Simulated down${left !== null ? `, back by itself in about ${left} min` : ''}. ` : ''}Fallback: {o.fallback}</small>
              </span>
              <button
                type="button"
                className={down ? 'btn btn-primary btn-sm' : 'btn btn-danger-outline btn-sm'}
                aria-label={`${down ? 'Restore' : 'Simulate outage of'} ${o.label}`}
                disabled={busy !== null || !status}
                onClick={() => void toggle(o.key, !down)}
              >
                {busy === o.key ? 'Saving…' : down ? 'Restore' : 'Simulate down'}
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

interface CopyButtonProps {
  text: string
  label: string
  onResult: (message: string) => void
}

function CopyButton({ text, label, onResult }: CopyButtonProps) {
  const [done, setDone] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])

  async function handleCopy(): Promise<void> {
    const ok = await copyText(text)
    onResult(ok ? `Copied ${label}.` : `Could not copy ${label}: select the text and copy it by hand.`)
    setDone(ok)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setDone(false), 2000)
  }
  return (
    <button type="button" className="btn btn-secondary btn-sm" onClick={() => void handleCopy()} aria-label={`Copy ${label}`}>
      {done ? 'Copied' : 'Copy'}
    </button>
  )
}

interface ShortcutsProps {
  onOpenRules: () => void
  onNotice: (text: string | null) => void
  onError: (text: string | null) => void
}

function ShortcutsPanel({ onOpenRules, onNotice, onError }: ShortcutsProps) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (confirming) cancelRef.current?.focus()
  }, [confirming])

  function cancel(): void {
    setConfirming(false)
    window.setTimeout(() => triggerRef.current?.focus(), 0)
  }

  async function reset(): Promise<void> {
    setBusy(true)
    onError(null)
    try {
      await post('/api/v1/admin/seed/reset', {})
      setConfirming(false)
      onNotice('Demo data restored. Everyone, including you, must sign in again (user IDs changed).')
    } catch (e) {
      onError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="eval-section" aria-labelledby="shortcuts-title">
      <h2 id="shortcuts-title">Demo shortcuts</h2>
      <div className="row">
        <button type="button" className="btn btn-secondary btn-sm" onClick={onOpenRules}>
          <Icon name="twin" size={18} /> Rules: Digital Twin and publish v2
        </button>
        <button ref={triggerRef} type="button" className="btn btn-danger-outline btn-sm" hidden={confirming} onClick={() => setConfirming(true)}>
          Reset demo data…
        </button>
      </div>
      {confirming && (
        <div className="confirm" role="group" aria-label="Confirm demo reset" onKeyDown={(e) => e.key === 'Escape' && cancel()}>
          <p>Reset all demo data to the seed? Claims, consents and payout changes made during the demo are wiped, faults and simulated outages end, and everyone is signed out. The audit log is kept.</p>
          <div className="row">
            <button type="button" className="btn btn-danger" disabled={busy} onClick={() => void reset()}>{busy ? 'Resetting…' : 'Yes, reset demo'}</button>
            <button ref={cancelRef} type="button" className="btn btn-secondary" onClick={cancel}>Cancel</button>
          </div>
        </div>
      )}
      <h3 className="viz-title">Persona logins (all mock, PIN 1234)</h3>
      <div className="table-wrap">
        <table className="table table-dense">
          <caption className="sr-only">Demo persona logins</caption>
          <thead><tr><th scope="col">Persona</th><th scope="col">Phone (mock)</th><th scope="col">What to show</th></tr></thead>
          <tbody>
            {PERSONAS.map((p) => (
              <tr key={p.phone}><th scope="row">{p.name}</th><td className="num">{p.phone}</td><td>{p.note}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">The sign-in screen also has one-tap demo buttons ("Demo accounts (mock)"). 5 wrong PINs lock only that account for 15 minutes.</p>
    </section>
  )
}

function ScamSamples() {
  const [copyStatus, setCopyStatus] = useState('')
  return (
    <section className="eval-section" aria-labelledby="samples-title">
      <h2 id="samples-title">Scam Shield: messages to paste</h2>
      <p className="muted">Sign in as Rafiq or Zainab, open "Is this message a scam?", paste the message and the sender.</p>
      <ul className="copy-list">
        {SCAM_SAMPLES.map((s) => (
          <li key={s.label} className="copy-item">
            <div className="eval-head"><strong>{s.label}</strong><Badge tone={s.expect === 'LIKELY_SCAM' ? 'risk' : s.expect === 'NOT_SURE' ? 'attn' : 'ok'}>expect {s.expect}</Badge></div>
            <q>{s.text}</q>
            <span className="muted">Sender: <code className="code">{s.sender}</code></span>
            <div className="row">
              <CopyButton text={s.text} label={`${s.label} message`} onResult={setCopyStatus} />
              <CopyButton text={s.sender} label={`${s.label} sender`} onResult={setCopyStatus} />
            </div>
          </li>
        ))}
      </ul>
      <p className="muted" role="status" aria-live="polite">{copyStatus}</p>
    </section>
  )
}

async function downloadSample(file: string): Promise<void> {
  const response = await fetch(apiUrl(`/api/v1/admin/judge/sample-docs/${encodeURIComponent(file)}`), {
    headers: { Authorization: `Bearer ${getToken() ?? ''}` },
  })
  if (response.status === 401) window.dispatchEvent(new Event(SESSION_ENDED_EVENT))
  if (!response.ok) throw new ApiError(response.status, 'DOWNLOAD_FAILED', 'Could not download that sample.')
  const url = URL.createObjectURL(await response.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = file
  a.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function SampleDocs({ onError }: { onError: (text: string | null) => void }) {
  const [docs, setDocs] = useState<SampleDoc[] | null>(null)
  useEffect(() => {
    let active = true
    api<SampleDoc[]>('/api/v1/admin/judge/sample-docs')
      .then((r) => active && setDocs(r.data))
      .catch((e: unknown) => active && onError(errorText(e)))
    return () => {
      active = false
    }
  }, [onError])

  async function handle(file: string): Promise<void> {
    try {
      await downloadSample(file)
    } catch (e) {
      onError(errorText(e))
    }
  }

  const edited = docs?.filter((d) => d.edited) ?? []
  const clean = docs?.filter((d) => !d.edited) ?? []
  return (
    <section className="eval-section" aria-labelledby="docs-title">
      <h2 id="docs-title">Sample documents (mock, watermarked)</h2>
      <p className="muted">Upload from Zainab's claim page ("Send photos of papers"). The edited certificate should be flagged for an officer; clean ones should pass.</p>
      {!docs && <p className="loading" role="status">Loading samples…</p>}
      {edited.length > 0 && (
        <>
          <h3 className="viz-title">Edited (should need a second look)</h3>
          <div className="dl-grid">{edited.map((d) => <DocButton key={d.file} doc={d} onClick={() => void handle(d.file)} />)}</div>
        </>
      )}
      {clean.length > 0 && (
        <details className="viz-table">
          <summary>Originals, WhatsApp copies and screenshots ({clean.length})</summary>
          <div className="dl-grid">{clean.map((d) => <DocButton key={d.file} doc={d} onClick={() => void handle(d.file)} />)}</div>
        </details>
      )}
    </section>
  )
}

function DocButton({ doc, onClick }: { doc: SampleDoc; onClick: () => void }) {
  return (
    <button type="button" className="btn btn-secondary btn-sm" onClick={onClick} aria-label={`Download ${doc.file}`}>
      <Icon name="document" size={18} /> {doc.file}
    </button>
  )
}

const FEED_MS = 10000

function ActivityFeed() {
  const [rows, setRows] = useState<ActivityRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [updated, setUpdated] = useState<string | null>(null)
  const [paused, setPaused] = useState(false)
  const holdRef = useRef(false) // paused: do not re-render the table under a reader or magnifier user
  const inFlight = useRef(false)
  useEffect(() => {
    holdRef.current = paused
  }, [paused])

  useEffect(() => {
    let active = true
    async function tick(): Promise<void> {
      if (document.hidden || holdRef.current || inFlight.current) return
      inFlight.current = true
      try {
        const data = (await api<ActivityRow[]>('/api/v1/admin/judge/activity')).data
        if (!active) return
        setRows(data)
        setUpdated(new Date().toISOString())
        setError(null)
      } catch (e) {
        if (active) setError(errorText(e))
      } finally {
        inFlight.current = false
      }
    }
    void tick()
    const id = window.setInterval(() => void tick(), FEED_MS)
    return () => {
      active = false
      window.clearInterval(id)
    }
  }, [])

  return (
    <section className="eval-section" aria-labelledby="feed-title">
      <div className="eval-head">
        <h2 id="feed-title">Recent activity (last 20 audit events)</h2>
        <button type="button" className="btn btn-secondary btn-sm" aria-pressed={paused} onClick={() => setPaused((v) => !v)}>
          {paused ? 'Resume updates' : 'Pause updates'}
        </button>
        <span className="muted">{paused ? 'Paused' : 'Refreshes every 10 s'}{updated ? `, last ${formatTime(updated)}` : ''}</span>
      </div>
      <ErrorNote message={error} />
      {!rows && !error && <p className="loading" role="status">Loading activity…</p>}
      {rows && rows.length === 0 && <p className="muted">No events yet. Sign in as a citizen and file a claim to see them here.</p>}
      {rows && rows.length > 0 && (
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Recent audit events (table)">
          <table className="table table-dense feed">
            <caption className="sr-only">Recent audit events</caption>
            <thead><tr><th scope="col">#</th><th scope="col">When</th><th scope="col">Actor</th><th scope="col">Action</th><th scope="col">Reason code</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.seq} className={/DENIED|LOCKED|REFUSED/.test(r.action) ? 'is-denied' : undefined}>
                  <td className="num">{r.seq}</td>
                  <td className="num">{formatTime(r.ts)}</td>
                  <td>{r.role ?? r.actor_type}</td>
                  <td><code className="code">{r.action}</code></td>
                  <td>{r.reason ?? <span className="muted">-</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
