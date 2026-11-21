// Pure data transforms for the staff Evaluation page (no React, no DOM: unit-tested in unit/evalTransforms.test.ts).
// Shapes mirror backend/app/evaluation/* (GET /api/v1/eval/latest). Every field the page reads is optional-safe,
// because older committed samples may lack newer fields.

export type SweepPoint = {
  threshold: number
  total_cost: number
  wrong_approvals: number
  delayed_genuine: number
  auto_approve_rate: number
  needs_person_rate: number
}

export type ClaimsEval = {
  n_cases: number
  n_should_approve: number
  cost_wrong_approval: number
  cost_delay: number
  analytic_threshold?: number
  configured_threshold: number
  baseline_never_auto: number
  min_cost: { threshold: number; total_cost: number; range?: [number, number] }
  at_configured: SweepPoint & { ask_proof_rate: number; human_rate: number }
  wrong_approvals_by_kind_at_configured: Record<string, number>
  sweep: SweepPoint[]
}

export type RateBlock = { n: number; MATCH: number; ASK: number; UNSURE: number; match_rate: number }

export type NamesEval = {
  n_pairs: number
  n_same_person: number
  n_different_person: number
  false_match_rate: number
  false_non_match_rate: number
  ask_rate: number
  unsure_rate: number
  exact_cnic_impostor?: RateBlock & { false_match_rate: number }
}

export type TierEval = {
  tier: string
  status: 'ran' | 'not_run'
  reason?: string
  note?: string
  n?: number
  accuracy?: number
  fpr?: number
  fnr?: number
  not_sure_rate?: number
  undecided_rate?: number
  median_latency_ms?: number
  p95_latency_ms?: number
  total_cost_usd?: number
  cost_per_check_usd?: number
  second_sensor_calls?: number
  model_id?: string | string[] | null
  models?: string[]
  items?: { latency_ms: number; cost_usd: number }[]
}

export type TierSet = Record<string, TierEval>

export type EvalResult = {
  prototype: boolean
  note: string
  generated_at: string
  source?: string
  ruleset_version: number | null
  claims: ClaimsEval
  names: NamesEval
  scam: { mode: string; n: number; n_scam: number; n_genuine: number; tiers: TierSet }
  documents: { set: string; positive: string; tiers: TierSet }
  reference_live?: { generated_at: string; source: string; scam_tiers: TierSet; document_tiers: TierSet } | null
  derived_note?: string
}

export const TIER_ORDER = ['deterministic', 'jev_only', 'cascade'] as const
export const TIER_LABEL: Record<string, string> = {
  deterministic: 'Deterministic only (no AI)',
  jev_only: 'Jev only',
  cascade: 'Full cascade',
}

// ---------- number formatting ----------

export function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return 'n/a'
  return `${(value * 100).toFixed(digits)}%`
}

export function ms(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'n/a'
  if (value < 1) return '< 1 ms'
  if (value >= 1000) return `${(value / 1000).toFixed(1)} s`
  return `${Math.round(value)} ms`
}

export function usd(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'n/a'
  if (value === 0) return '$0'
  if (value < 0.001) return `$${value.toFixed(5)}`
  return `$${value.toFixed(4)}`
}

// ---------- claims: cost curve ----------

/** Threshold that minimises expected cost for one claim: approve when p >= C_wrong / (C_wrong + C_delay). */
export function breakEvenThreshold(costWrong: number, costDelay: number): number {
  if (costWrong <= 0 && costDelay <= 0) return 0
  return costWrong / (costWrong + costDelay)
}

export type CurvePoint = { x: number; y: number; wrong: number; delayed: number; autoRate: number }

export function costCurve(claims: ClaimsEval): CurvePoint[] {
  return [...(claims.sweep ?? [])]
    .sort((a, b) => a.threshold - b.threshold)
    .map((p) => ({ x: p.threshold, y: p.total_cost, wrong: p.wrong_approvals, delayed: p.delayed_genuine, autoRate: p.auto_approve_rate }))
}

/** True when every point on the curve has the same cost (the honest "the threshold does not matter here" case). */
export function isFlat(points: CurvePoint[]): boolean {
  return points.length > 0 && points.every((p) => p.y === points[0].y)
}

export function nearestIndex(points: { x: number }[], x: number): number {
  let best = 0
  for (let i = 1; i < points.length; i += 1) {
    if (Math.abs(points[i].x - x) < Math.abs(points[best].x - x)) best = i
  }
  return best
}

export type Bar = { key: string; label: string; value: number; display: string; detail?: string }

export function wrongApprovalBars(claims: ClaimsEval): Bar[] {
  return Object.entries(claims.wrong_approvals_by_kind_at_configured ?? {})
    .sort((a, b) => b[1] - a[1])
    .map(([kind, count]) => ({ key: kind, label: kind, value: count, display: String(count), detail: `${count} of ${claims.n_cases} synthetic claims` }))
}

// ---------- names ----------

export function nameRateBars(names: NamesEval): Bar[] {
  return [
    { key: 'false_match', label: 'False match (different person matched)', value: names.false_match_rate,
      display: pct(names.false_match_rate, 1), detail: `of ${names.n_different_person} different-person pairs` },
    { key: 'false_non_match', label: 'False non-match (same person not matched)', value: names.false_non_match_rate,
      display: pct(names.false_non_match_rate, 1), detail: `of ${names.n_same_person} same-person pairs` },
    { key: 'ask', label: 'Ask for proof', value: names.ask_rate, display: pct(names.ask_rate, 1), detail: `of all ${names.n_pairs} pairs` },
    { key: 'unsure', label: 'Unsure (officer)', value: names.unsure_rate, display: pct(names.unsure_rate, 1), detail: `of all ${names.n_pairs} pairs` },
  ]
}

// ---------- tiers (Scam Shield and documents) ----------

export function percentile95(values: number[]): number | null {
  if (values.length === 0) return null
  const ordered = [...values].sort((a, b) => a - b)
  return ordered[Math.min(ordered.length - 1, Math.round(0.95 * (ordered.length - 1)))]
}

export type TierRow = {
  key: string
  label: string
  ran: boolean
  reason?: string
  note?: string
  accuracy: number | null
  fpr: number | null
  fnr: number | null
  undecided: number | null
  medianMs: number | null
  p95Ms: number | null
  costPerCheck: number | null
  models: string[]
  sensorCalls: number | null
  n: number | null
}

function modelsOf(tier: TierEval): string[] {
  if (tier.models) return tier.models
  if (Array.isArray(tier.model_id)) return tier.model_id
  return tier.model_id ? [tier.model_id] : []
}

export function tierRow(key: string, tier: TierEval | undefined): TierRow {
  const label = TIER_LABEL[key] ?? key
  if (!tier || tier.status !== 'ran') {
    return { key, label, ran: false, reason: tier?.reason ?? 'not run', accuracy: null, fpr: null, fnr: null, undecided: null,
      medianMs: null, p95Ms: null, costPerCheck: null, models: [], sensorCalls: null, n: null }
  }
  const items = tier.items ?? []
  const n = tier.n ?? items.length
  const p95 = tier.p95_latency_ms ?? percentile95(items.map((i) => i.latency_ms))
  const perCheck = tier.cost_per_check_usd ?? (tier.total_cost_usd !== undefined && n ? tier.total_cost_usd / n : null)
  return {
    key, label, ran: true, note: tier.note, n,
    accuracy: tier.accuracy ?? null, fpr: tier.fpr ?? null, fnr: tier.fnr ?? null,
    undecided: tier.not_sure_rate ?? tier.undecided_rate ?? null,
    medianMs: tier.median_latency_ms ?? null, p95Ms: p95, costPerCheck: perCheck,
    models: modelsOf(tier), sensorCalls: tier.second_sensor_calls ?? null,
  }
}

export type TierTable = { rows: TierRow[]; fromReference: boolean; referenceAt: string | null }

/**
 * Rows in fixed tier order. An offline re-run cannot call Jev or the second sensor; when its AI tiers are
 * "not run" and a labelled live reference exists, show the reference tiers instead and say so.
 */
export function tierTable(current: TierSet, reference: TierSet | undefined, referenceAt: string | null | undefined): TierTable {
  const aiRan = TIER_ORDER.some((k) => k !== 'deterministic' && current[k]?.status === 'ran')
  const useReference = !aiRan && !!reference && TIER_ORDER.some((k) => reference[k]?.status === 'ran')
  const source = useReference && reference ? reference : current
  return { rows: TIER_ORDER.map((k) => tierRow(k, source[k])), fromReference: useReference, referenceAt: useReference ? referenceAt ?? null : null }
}

export function accuracyBars(rows: TierRow[]): Bar[] {
  return rows.filter((r) => r.ran && r.accuracy !== null).map((r) => ({
    key: r.key, label: r.label, value: r.accuracy ?? 0, display: pct(r.accuracy),
    detail: `undecided ${pct(r.undecided)}, FPR ${pct(r.fpr)}, FNR ${pct(r.fnr)}`,
  }))
}

// ---------- chart geometry ----------

/** About `count` round tick values covering [min, max] (1, 2, 2.5 or 5 times a power of ten). */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (!(max > min)) return [min]
  const raw = (max - min) / Math.max(1, count)
  const power = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? 10 * power
  const start = Math.ceil(min / step) * step
  const ticks: number[] = []
  for (let v = start; v <= max + step * 1e-9; v += step) ticks.push(Number(v.toFixed(10)))
  return ticks
}

export function linearScale(domain: [number, number], range: [number, number]): (v: number) => number {
  const [d0, d1] = domain
  const [r0, r1] = range
  const span = d1 - d0 || 1
  return (v: number) => r0 + ((v - d0) / span) * (r1 - r0)
}

/** Upper bound for a cost axis: the larger of the curve and the baseline, rounded up to a nice tick. */
export function costAxisMax(points: CurvePoint[], baseline: number): number {
  const top = Math.max(baseline, ...points.map((p) => p.y), 1)
  const ticks = niceTicks(0, top * 1.1, 4)
  return Math.max(ticks[ticks.length - 1], top)
}
