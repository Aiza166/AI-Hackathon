// Unit tests for the Evaluation page data transforms. Run: npm run test:unit
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  accuracyBars, breakEvenThreshold, costAxisMax, costCurve, isFlat, linearScale, ms, nameRateBars, nearestIndex,
  niceTicks, pct, percentile95, tierRow, tierTable, usd, wrongApprovalBars,
} from '../src/lib/evalTransforms.ts'
import type { ClaimsEval, NamesEval, TierSet } from '../src/lib/evalTransforms.ts'

const point = (threshold: number, cost: number, wrong = 2) => ({
  threshold, total_cost: cost, wrong_approvals: wrong, delayed_genuine: 70, auto_approve_rate: 0.31, needs_person_rate: 0.69,
})

const CLAIMS: ClaimsEval = {
  n_cases: 200, n_should_approve: 130, cost_wrong_approval: 20, cost_delay: 1, analytic_threshold: 0.9524,
  configured_threshold: 0.95, baseline_never_auto: 130,
  min_cost: { threshold: 0.5, total_cost: 110 },
  at_configured: { ...point(0.95, 110), ask_proof_rate: 0.235, human_rate: 0.455 },
  wrong_approvals_by_kind_at_configured: { 'stolen CNIC': 1, 'identity theft with full credentials': 2 },
  sweep: [point(0.97, 120, 1), point(0.5, 110), point(0.95, 110)],
}

test('break-even threshold for a 20:1 cost ratio is 20/21', () => {
  assert.equal(breakEvenThreshold(20, 1).toFixed(4), '0.9524')
  assert.equal(breakEvenThreshold(0, 0), 0)
})

test('cost curve is sorted by threshold and keeps wrong approvals for the tooltip', () => {
  const curve = costCurve(CLAIMS)
  assert.deepEqual(curve.map((p) => p.x), [0.5, 0.95, 0.97])
  assert.equal(curve[2].wrong, 1)
  assert.equal(CLAIMS.sweep[0].threshold, 0.97, 'input is not mutated')
})

test('flat detection is honest about a curve where the threshold does not matter', () => {
  assert.equal(isFlat(costCurve(CLAIMS)), false)
  assert.equal(isFlat(costCurve({ ...CLAIMS, sweep: [point(0.5, 110), point(0.9, 110)] })), true)
  assert.equal(isFlat([]), false)
})

test('nearest index snaps the crosshair to the closest threshold', () => {
  const curve = costCurve(CLAIMS)
  assert.equal(nearestIndex(curve, 0.94), 1)
  assert.equal(nearestIndex(curve, 0.1), 0)
  assert.equal(nearestIndex(curve, 2), 2)
})

test('cost axis always includes the never-auto-approve baseline', () => {
  assert.ok(costAxisMax(costCurve(CLAIMS), 130) >= 130)
  assert.ok(costAxisMax(costCurve(CLAIMS), 500) >= 500)
})

test('wrong approvals are ranked by count', () => {
  const bars = wrongApprovalBars(CLAIMS)
  assert.deepEqual(bars.map((b) => b.value), [2, 1])
  assert.match(bars[0].detail ?? '', /of 200/)
})

test('name matching bars carry the four rates as percentages', () => {
  const names: NamesEval = { n_pairs: 502, n_same_person: 250, n_different_person: 252, false_match_rate: 0,
    false_non_match_rate: 0.42, ask_rate: 0.2729, unsure_rate: 0.4382 }
  const bars = nameRateBars(names)
  assert.deepEqual(bars.map((b) => b.key), ['false_match', 'false_non_match', 'ask', 'unsure'])
  assert.equal(bars[0].display, '0.0%')
  assert.equal(bars[1].display, '42.0%')
})

test('tier row derives p95 and cost per check from items when the summary lacks them', () => {
  const row = tierRow('cascade', { tier: 'cascade', status: 'ran', n: 4, accuracy: 0.8, fpr: 0, fnr: 0, undecided_rate: 0.2,
    median_latency_ms: 500, total_cost_usd: 0.004, model_id: 'jev-1.14.0',
    items: [100, 200, 300, 4000].map((latency_ms) => ({ latency_ms, cost_usd: 0.001 })) })
  assert.equal(row.p95Ms, 4000)
  assert.equal(row.costPerCheck, 0.001)
  assert.equal(row.undecided, 0.2)
  assert.deepEqual(row.models, ['jev-1.14.0'])
})

test('a tier that did not run is shown as not run, never as zero', () => {
  const row = tierRow('jev_only', { tier: 'jev_only', status: 'not_run', reason: 'needs the Jev API key (live run)' })
  assert.equal(row.ran, false)
  assert.equal(row.accuracy, null)
  assert.match(row.reason ?? '', /Jev/)
})

test('offline re-run falls back to the labelled live reference for the tier table', () => {
  const offline: TierSet = {
    deterministic: { tier: 'deterministic', status: 'ran', n: 80, accuracy: 0.125 },
    jev_only: { tier: 'jev_only', status: 'not_run' },
    cascade: { tier: 'cascade', status: 'not_run' },
  }
  const live: TierSet = {
    deterministic: { tier: 'deterministic', status: 'ran', n: 80, accuracy: 0.125 },
    jev_only: { tier: 'jev_only', status: 'ran', n: 80, accuracy: 0.74, models: ['jev-1.14.0'] },
    cascade: { tier: 'cascade', status: 'ran', n: 80, accuracy: 0.84, models: ['gpt-5-mini', 'jev-1.14.0'] },
  }
  const table = tierTable(offline, live, '2026-11-21T11:08:34+00:00')
  assert.equal(table.fromReference, true)
  assert.equal(table.referenceAt, '2026-11-21T11:08:34+00:00')
  assert.deepEqual(table.rows.map((r) => r.key), ['deterministic', 'jev_only', 'cascade'])
  assert.deepEqual(table.rows[2].models, ['gpt-5-mini', 'jev-1.14.0'])
  const own = tierTable(live, undefined, null)
  assert.equal(own.fromReference, false)
  const none = tierTable(offline, undefined, null)
  assert.equal(none.fromReference, false)
  assert.equal(none.rows[1].ran, false)
  assert.equal(accuracyBars(none.rows).length, 1)
})

test('formatting helpers', () => {
  assert.equal(pct(0.8375), '84%')
  assert.equal(pct(undefined), 'n/a')
  assert.equal(ms(0.4), '< 1 ms')
  assert.equal(ms(5311.5), '5.3 s')
  assert.equal(ms(450.7), '451 ms')
  assert.equal(usd(0), '$0')
  assert.equal(usd(0.00040565), '$0.00041')
})

test('percentile and scales', () => {
  assert.equal(percentile95([]), null)
  assert.equal(percentile95([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]), 19)
  assert.deepEqual(niceTicks(0, 143, 4), [0, 50, 100])
  assert.deepEqual(niceTicks(0.5, 1, 5), [0.5, 0.6, 0.7, 0.8, 0.9, 1])
  const x = linearScale([0.5, 1], [0, 100])
  assert.equal(x(0.75), 50)
})
