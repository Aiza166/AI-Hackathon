import { useCallback, useEffect, useState } from 'react'
import { api, errorText, post } from '../api/client'
import type { RuleVersionRow, Simulation, TwinCase } from '../api/types'
import { Badge, ErrorNote, Loading, toneFor } from '../components/ui'
import { Icon } from '../lib/icons'
import { AuditorHome } from './AuditorHome'

// Admin: versioned eligibility rules (Digital Twin + publish) and the audit log.

type Tab = 'rules' | 'audit'

export function AdminHome() {
  const [tab, setTab] = useState<Tab>('rules')
  return (
    <div className="stack-lg">
      <div className="tabs" role="tablist" aria-label="Admin sections">
        <button type="button" role="tab" id="tab-rules" aria-selected={tab === 'rules'} aria-controls="panel-admin" className="tab" onClick={() => setTab('rules')}>
          <Icon name="rules" size={20} /> Rules
        </button>
        <button type="button" role="tab" id="tab-audit" aria-selected={tab === 'audit'} aria-controls="panel-admin" className="tab" onClick={() => setTab('audit')}>
          <Icon name="shield" size={20} /> Audit log
        </button>
      </div>
      <div role="tabpanel" id="panel-admin" aria-labelledby={`tab-${tab}`}>
        {tab === 'rules' ? <RulesPanel /> : <AuditorHome embedded />}
      </div>
    </div>
  )
}

function RulesPanel() {
  const [rules, setRules] = useState<RuleVersionRow[] | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async (): Promise<RuleVersionRow[] | null> => {
    try {
      const rows = (await api<RuleVersionRow[]>('/api/v1/admin/rules')).data
      setRules(rows)
      return rows
    } catch (e) {
      setError(errorText(e))
      return null
    }
  }, [])

  useEffect(() => {
    void load().then((rows) => {
      if (!rows) return
      const pick = rows.find((r) => r.status === 'draft') ?? rows.find((r) => r.status === 'live') ?? rows[0]
      setSelectedId((current) => current ?? pick?.id ?? null)
    })
  }, [load])

  async function handlePublished(version: number): Promise<void> {
    setNotice(`Version ${version} is now live. New claims are decided under it; past decisions keep their own version.`)
    await load()
  }

  const selected = rules?.find((r) => r.id === selectedId) ?? null

  return (
    <div className="split">
      <section className="split-narrow" aria-labelledby="versions-title">
        <div className="page-head">
          <h1 id="versions-title" className="page-title">Rule versions</h1>
        </div>
        <p className="page-sub">Eligibility rules are data. Every decision stores the version it used.</p>
        <ErrorNote message={error} />
        {!rules && !error && <Loading label="Loading rules" />}
        <ul className="versions">
          {rules?.map((r) => (
            <li key={r.id}>
              <button type="button" className={r.id === selectedId ? 'version is-selected' : 'version'} aria-pressed={r.id === selectedId} onClick={() => setSelectedId(r.id)}>
                <span className="version-n">v{r.version}</span>
                <span className="version-label">{r.label}</span>
                <Badge tone={toneFor(r.status)}>{r.status}</Badge>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="split-side split-wide" aria-label="Version detail">
        {notice && <p className="note note-ok" role="status"><Icon name="check" size={20} /><span>{notice}</span></p>}
        {selected ? <VersionDetail key={selected.id} rule={selected} onPublished={handlePublished} /> : null}
      </section>
    </div>
  )
}

interface VersionDetailProps {
  rule: RuleVersionRow
  onPublished: (version: number) => Promise<void>
}

function VersionDetail({ rule, onPublished }: VersionDetailProps) {
  const [sim, setSim] = useState<Simulation | null>(null)
  const [busy, setBusy] = useState<'sim' | 'pub' | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isDraft = rule.status === 'draft'

  async function simulate(): Promise<void> {
    setBusy('sim')
    setError(null)
    try {
      setSim((await post<Simulation>(`/api/v1/rules/${rule.id}/simulate`, {})).data)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(null)
    }
  }

  async function publish(): Promise<void> {
    setBusy('pub')
    setError(null)
    try {
      const result = await post<{ version: number }>(`/api/v1/rules/${rule.id}/publish`, {})
      setConfirming(false)
      await onPublished(result.data.version)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <article className="detail">
      <header className="detail-head">
        <h2 className="detail-title">Version {rule.version}</h2>
        <Badge tone={toneFor(rule.status)}>{rule.status}</Badge>
      </header>
      <p>{rule.label}</p>
      <dl className="facts facts-inline">
        <dt>Ruleset</dt><dd>{rule.ruleset}</dd>
        <dt>Effective from</dt><dd>{rule.effective_from ?? 'Always'}</dd>
        {Object.entries(rule.thresholds).map(([k, v]) => (
          <ThresholdRow key={k} name={k} value={v} />
        ))}
      </dl>

      <details className="rule-list">
        <summary>{rule.rules.length} rules in this version</summary>
        <ol>
          {rule.rules.map((r) => (
            <li key={r.id}>
              <strong>{r.title ?? r.id}</strong>
              {r.basis && <span className="muted"> {r.basis}</span>}
              {r.reason && <code className="code">{r.reason}</code>}
            </li>
          ))}
        </ol>
      </details>

      <ErrorNote message={error} />
      {isDraft && (
        <div className="twin-actions">
          <button type="button" className="btn btn-secondary" disabled={busy !== null} onClick={() => void simulate()}>
            <Icon name="twin" size={20} /> {busy === 'sim' ? 'Running…' : sim ? 'Run Digital Twin again' : 'Run Digital Twin'}
          </button>
          {!confirming && (
            <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={() => setConfirming(true)}>
              Publish v{rule.version}
            </button>
          )}
        </div>
      )}
      {isDraft && confirming && (
        <div className="confirm" role="group" aria-label="Confirm publish">
          <p>
            Publish version {rule.version}? The current live version will be retired.
            {sim ? ` The Digital Twin found ${sim.changed} of ${sim.checked} past cases would be decided differently.` : ' You have not run the Digital Twin yet.'}
          </p>
          <div className="row">
            <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={() => void publish()}>
              {busy === 'pub' ? 'Publishing…' : `Yes, publish v${rule.version}`}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setConfirming(false)}>Cancel</button>
          </div>
        </div>
      )}
      {sim && <TwinTable sim={sim} />}
    </article>
  )
}

function ThresholdRow({ name, value }: { name: string; value: number }) {
  return (
    <>
      <dt>{name.replace(/_/g, ' ')}</dt>
      <dd>{value}</dd>
    </>
  )
}

function TwinTable({ sim }: { sim: Simulation }) {
  return (
    <section className="twin" aria-labelledby="twin-title">
      <h3 id="twin-title" className="twin-title">
        Digital Twin: <strong>{sim.changed}</strong> of {sim.checked} past cases would change under v{sim.draft_version}
      </h3>
      <p className="muted">Nothing was saved. Changed rows are highlighted.</p>
      <div className="table-wrap">
        <table className="table table-dense">
          <thead>
            <tr><th scope="col">Case</th><th scope="col">Route</th><th scope="col">Paid until</th><th scope="col">Reasons</th></tr>
          </thead>
          <tbody>
            {sim.cases.map((c) => <TwinRow key={c.case} row={c} />)}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Delta({ before, after, changed }: { before: string; after: string; changed: boolean }) {
  if (!changed) return <span>{before}</span>
  return (
    <span className="delta">
      <s className="delta-before">{before}</s>
      <Icon name="arrow-right" size={14} />
      <strong className="delta-after">{after}</strong>
    </span>
  )
}

function TwinRow({ row }: { row: TwinCase }) {
  const changed = row.changed.length > 0
  return (
    <tr className={changed ? 'is-changed' : undefined}>
      <th scope="row">{row.case}</th>
      <td><Delta before={row.before.route} after={row.after.route} changed={row.changed.includes('route')} /></td>
      <td><Delta before={row.before.entitlement_end ?? 'No limit'} after={row.after.entitlement_end ?? 'No limit'} changed={row.changed.includes('entitlement_end')} /></td>
      <td className="codes">
        <Delta before={row.before.reasons.join(', ') || '-'} after={row.after.reasons.join(', ') || '-'} changed={row.changed.includes('reasons')} />
      </td>
    </tr>
  )
}
