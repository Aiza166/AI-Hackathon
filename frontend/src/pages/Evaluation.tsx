import { useCallback, useEffect, useRef, useState } from 'react'
import { api, errorText, post } from '../api/client'
import { BarChart, CostCurveChart } from '../components/charts'
import { Badge, ErrorNote, formatTime } from '../components/ui'
import { Icon } from '../lib/icons'
import type { EvalResult, TierTable } from '../lib/evalTransforms'
import {
  accuracyBars, breakEvenThreshold, costCurve, isFlat, ms, nameRateBars, pct, tierTable, usd, wrongApprovalBars,
} from '../lib/evalTransforms'
import './staff-console.css'

// Staff Evaluation page (officer, admin, auditor): the measured numbers behind the thresholds and the
// model choices, on synthetic test sets. Lazy-loaded; never part of the citizen bundle.

type Busy = 'run' | 'live' | null

export function Evaluation({ canRunLive = false }: { canRunLive?: boolean }) {
  const [result, setResult] = useState<EvalResult | null>(null)
  const [busy, setBusy] = useState<Busy>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  // Only the newest request may set the result: a slow initial load must not overwrite a re-run.
  const latestRequest = useRef(0)
  const mounted = useRef(true)

  const load = useCallback(async () => {
    const request = ++latestRequest.current
    try {
      const data = (await api<EvalResult>('/api/v1/eval/latest')).data
      if (mounted.current && request === latestRequest.current) setResult(data)
    } catch (e) {
      if (mounted.current && request === latestRequest.current) setError(errorText(e))
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void load()
    return () => {
      mounted.current = false
    }
  }, [load])

  async function rerun(live: boolean): Promise<void> {
    if (busy !== null) return
    const request = ++latestRequest.current
    setBusy(live ? 'live' : 'run')
    setError(null)
    setNotice(null)
    try {
      const fresh = (await post<EvalResult>(`/api/v1/eval/run${live ? '?live=true' : ''}`, {})).data
      if (!mounted.current || request !== latestRequest.current) return
      setResult(fresh)
      setNotice(live ? 'Live run finished (real Jev and second sensor calls).' : 'Re-run finished. Recorded in the audit log as EVAL_RUN.')
    } catch (e) {
      if (mounted.current) setError(errorText(e))
    } finally {
      if (mounted.current) setBusy(null)
    }
  }

  return (
    <div className="stack-lg viz-root">
      <header className="eval-head">
        <div className="stack">
          <h1 className="page-title">Evaluation</h1>
          <p className="page-sub">
            How the prototype behaves on <strong>synthetic test sets we built ourselves</strong> (mock data, fixed seeds).
            These numbers show where the code is safe and where it fails. They are not real-world accuracy.
          </p>
        </div>
        <div className="row">
          <button type="button" className="btn btn-secondary btn-sm" aria-disabled={busy !== null} onClick={() => void rerun(false)}>
            <Icon name="clock" size={18} /> {busy === 'run' ? 'Running…' : 'Re-run now'}
          </button>
          {canRunLive && (
            <button type="button" className="btn btn-primary btn-sm" aria-disabled={busy !== null} onClick={() => void rerun(true)}>
              {busy === 'live' ? 'Live run (several minutes)…' : 'Run live (Jev + gpt-5-mini)'}
            </button>
          )}
        </div>
      </header>
      <ErrorNote message={error} />
      <div role="status" aria-live="polite">
        {notice && <p className="note note-ok"><Icon name="check" size={20} /><span>{notice}</span></p>}
        {busy !== null && <p className="muted">{busy === 'live' ? 'Live run in progress: this calls Jev and gpt-5-mini and takes several minutes.' : 'Re-running…'}</p>}
      </div>
      {!result && !error && <p className="loading" role="status">Loading evaluation…</p>}
      {result && <EvalBody result={result} />}
    </div>
  )
}

function RunLine({ result }: { result: EvalResult }) {
  const source = result.source === 'committed_sample' ? 'committed sample in the repo' : 'run in this server process'
  return (
    <p className="muted">
      <span className="eval-label">Synthetic test set</span>{' '}
      Generated {formatTime(result.generated_at)} ({source}), rule version v{result.ruleset_version ?? '?'}, Scam Shield mode: {result.scam.mode}.
    </p>
  )
}

function EvalBody({ result }: { result: EvalResult }) {
  return (
    <>
      <RunLine result={result} />
      <ClaimsSection result={result} />
      <NamesSection result={result} />
      <TierSection
        id="scam"
        title="Scam Shield: three sensor tiers"
        intro={`${result.scam.n} invented messages and call scripts (${result.scam.n_scam} scam, ${result.scam.n_genuine} genuine). Accuracy counts NOT SURE as not correct. FPR = genuine called a scam; FNR = scam called genuine (the dangerous miss).`}
        table={tierTable(result.scam.tiers, result.reference_live?.scam_tiers, result.reference_live?.generated_at)}
        undecidedLabel="NOT SURE"
      />
      <TierSection
        id="docs"
        title="Document checks: three sensor tiers"
        intro="The 20 mock images in backend/sample_docs; positive = the edited death certificate (original + WhatsApp copy). A document is never called fake: a flag means 'needs a second look' by an officer."
        table={tierTable(result.documents.tiers, result.reference_live?.document_tiers, result.reference_live?.generated_at)}
        undecidedLabel="Undecided"
      />
      <ModelStory />
      {result.derived_note && <p className="muted">{result.derived_note}</p>}
    </>
  )
}

function ClaimsSection({ result }: { result: EvalResult }) {
  const c = result.claims
  const points = costCurve(c)
  const flat = isFlat(points)
  const breakEven = breakEvenThreshold(c.cost_wrong_approval, c.cost_delay)
  const bars = wrongApprovalBars(c)
  const at = c.at_configured
  return (
    <section className="eval-section" aria-labelledby="claims-title">
      <h2 id="claims-title">Claims: the cost of being wrong</h2>
      <p className="eval-why">
        <strong>Why 0.95:</strong> paying the wrong person is about {c.cost_wrong_approval} times worse than making a genuine
        widow wait, so we auto-approve only when we are at least {c.cost_wrong_approval}/{c.cost_wrong_approval + c.cost_delay} = {breakEven.toFixed(3)} sure,
        rounded to {c.configured_threshold}; everything else goes to a person.
      </p>
      <div className="stat-row">
        <Stat tone="risk" value={String(at.wrong_approvals)} label={`wrong approvals of ${c.n_cases} at ${c.configured_threshold}`} />
        <Stat tone="info" value={String(at.total_cost)} label={`total cost (never auto-approve: ${c.baseline_never_auto})`} />
        <Stat tone="attn" value={pct(at.needs_person_rate)} label="need a person (ask for proof or officer)" />
        <Stat tone="ok" value={pct(at.auto_approve_rate)} label="auto-approved" />
      </div>
      <CostCurveChart
        points={points}
        baseline={c.baseline_never_auto}
        configured={c.configured_threshold}
        title={`Total cost = ${c.cost_wrong_approval} x wrong approvals + ${c.cost_delay} x delayed genuine claims, by threshold (${c.n_cases} synthetic claims)`}
      />
      {flat && (
        <p className="note note-info">
          <Icon name="question" size={20} />
          <span>
            Honest reading: the curve is flat ({points[0].y} at every threshold from {points[0].x.toFixed(2)} to {points[points.length - 1].x.toFixed(2)}).
            On this set the threshold is not what keeps people safe; hard red flags (payee, duplicate, already drawing),
            "no match without an exact CNIC" and "her typed DOB must equal the record" do that.
          </span>
        </p>
      )}
      <div className="eval-grid">
        {bars.length > 1 ? (
          <BarChart bars={bars} title={`Wrong approvals at ${c.configured_threshold}, by kind`} valueHeader="Count" />
        ) : (
          <div className="stack">
            <h3 className="viz-title">Wrong approvals at {c.configured_threshold}, by kind</h3>
            {bars.length === 0 ? <p>None on this set.</p> : (
              <p><strong>{bars[0].value}</strong> x {bars[0].label}: exact CNIC, exact name and exact DOB. No data match can tell them apart from the widow; in the app this needs her phone and PIN or a consenting helper.</p>
            )}
          </div>
        )}
        <dl className="status-list">
          <dt>Human review rate</dt><dd>{pct(at.needs_person_rate)} ({pct(at.ask_proof_rate)} asked for proof, {pct(at.human_rate)} to an officer)</dd>
          <dt>Cheapest threshold</dt><dd>{c.min_cost.threshold} (cost {c.min_cost.total_cost}){flat ? ', first of many equal points' : ''}</dd>
          <dt>Never auto-approve</dt><dd>cost {c.baseline_never_auto}: every genuine claim waits</dd>
          <dt>Delayed genuine claims</dt><dd>{at.delayed_genuine} of {c.n_should_approve}</dd>
        </dl>
      </div>
    </section>
  )
}

function NamesSection({ result }: { result: EvalResult }) {
  const n = result.names
  return (
    <section className="eval-section" aria-labelledby="names-title">
      <h2 id="names-title">Name matching</h2>
      <p className="muted">
        {n.n_pairs} synthetic identity pairs: {n.n_same_person} same person with spelling variants, {n.n_different_person} hard
        look-alikes (same name, siblings, CNIC one digit off). Nothing matches without an exact CNIC and her exact DOB;
        everything else is asked or sent to an officer, which is slower but safe.
      </p>
      <BarChart bars={nameRateBars(n)} title="Name matching outcomes (synthetic pairs)" max={1} valueHeader="Rate" />
      {n.exact_cnic_impostor && (
        <p className="muted">
          Someone else's real CNIC with a guessed name: matched {pct(n.exact_cnic_impostor.match_rate, 1)} of {n.exact_cnic_impostor.n} tries.
        </p>
      )}
    </section>
  )
}

interface TierSectionProps {
  id: string
  title: string
  intro: string
  table: TierTable
  undecidedLabel: string
}

function TierSection({ id, title, intro, table, undecidedLabel }: TierSectionProps) {
  const bars = accuracyBars(table.rows)
  return (
    <section className="eval-section" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{title}</h2>
      <p className="muted">{intro}</p>
      {table.fromReference && (
        <p className="note note-attn">
          <Icon name="clock" size={20} />
          <span>
            This re-run had no AI keys (offline), so the AI tiers did not run. Showing the last live measurement
            {table.referenceAt ? ` from ${formatTime(table.referenceAt)}` : ''} instead.
          </span>
        </p>
      )}
      <div className="table-wrap" tabIndex={0} role="region" aria-label={`${title} (table, scrolls sideways)`}>
        <table className="table table-dense">
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr>
              <th scope="col">Tier</th><th scope="col">Accuracy</th><th scope="col">FPR</th><th scope="col">FNR</th>
              <th scope="col">{undecidedLabel}</th><th scope="col">Median</th><th scope="col">p95</th>
              <th scope="col">Cost / check</th><th scope="col">Models</th>
            </tr>
          </thead>
          <tbody>
            {table.rows.map((r) => (
              <tr key={r.key}>
                <th scope="row">{r.label}{r.sensorCalls ? <span className="muted"> (second sensor on {r.sensorCalls} of {r.n})</span> : null}</th>
                {r.ran ? (
                  <>
                    <td className="num">{pct(r.accuracy)}</td><td className="num">{pct(r.fpr)}</td><td className="num">{pct(r.fnr)}</td>
                    <td className="num">{pct(r.undecided)}</td><td className="num">{ms(r.medianMs)}</td><td className="num">{ms(r.p95Ms)}</td>
                    <td className="num">{usd(r.costPerCheck)}</td>
                    <td>{r.models.length ? <span className="models">{r.models.map((m) => <code key={m} className="code">{m}</code>)}</span> : <span className="muted">none (code only)</span>}</td>
                  </>
                ) : (
                  <td colSpan={8} className="muted">Not run: {r.reason}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {bars.length > 1 && <BarChart bars={bars} title={`${title.split(':')[0]}: accuracy by tier`} max={1} valueHeader="Accuracy" />}
    </section>
  )
}

function ModelStory() {
  return (
    <section className="eval-section" aria-labelledby="models-title">
      <h2 id="models-title">Model and tool selection</h2>
      <ul className="stack">
        <li><Badge tone="quiet">code</Badge> Deterministic checks (keywords, link parser, caller rules, stamp copy-move) run on everything: free, under a millisecond, and they never say "looks genuine" alone.</li>
        <li><Badge tone="info">jev-1.14.0</Badge> Jev, a cheap sensor, answers small yes/no questions on every check (about 0.3-0.5 s). Code decides; Jev is never asked "is this a scam?".</li>
        <li><Badge tone="attn">gpt-5-mini</Badge> The stronger second sensor is called only on hard cases: when Jev is undecided or contradicts the rules. Disagreement means NOT SURE and a person looks.</li>
      </ul>
    </section>
  )
}

function Stat({ tone, value, label }: { tone: 'ok' | 'attn' | 'risk' | 'info'; value: string; label: string }) {
  return (
    <div className={`stat tone-${tone}`}>
      <span className="stat-n">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}
