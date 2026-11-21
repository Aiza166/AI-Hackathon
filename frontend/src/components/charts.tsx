import { useId, useState } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'
import type { Bar, CurvePoint } from '../lib/evalTransforms'
import { costAxisMax, linearScale, nearestIndex, niceTicks, pct } from '../lib/evalTransforms'

// Hand-rolled, accessible SVG charts for the staff Evaluation page (no chart library: keeps the staff chunk small).
// Follows the dataviz method: one series colour (slot 1), 2px lines, >= 8px markers with a surface ring,
// hairline grid, legend for >= 2 series, hover + keyboard readout, and a table view for every chart.

const W = 640
const H = 280
const M = { top: 20, right: 20, bottom: 44, left: 52 }

interface CostCurveProps {
  points: CurvePoint[]
  baseline: number
  configured: number
  title: string
}

/** Total cost vs auto-approval threshold, with the configured threshold and the "never auto-approve" baseline. */
export function CostCurveChart({ points, baseline, configured, title }: CostCurveProps) {
  const id = useId()
  const configuredIndex = nearestIndex(points, configured)
  const [active, setActive] = useState<number | null>(null)
  if (points.length === 0) return <p className="muted">No sweep data in this run.</p>

  const xMin = Math.floor(points[0].x * 10) / 10
  const xMax = Math.max(1, points[points.length - 1].x)
  const yMax = costAxisMax(points, baseline)
  const x = linearScale([xMin, xMax], [M.left, W - M.right])
  const y = linearScale([0, yMax], [H - M.bottom, M.top])
  const yTicks = niceTicks(0, yMax, 4)
  const xTicks = niceTicks(xMin, xMax, 5)
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.x).toFixed(1)},${y(p.y).toFixed(1)}`).join(' ')
  // Clamp: a re-run can bring fewer points than the index a keyboard user left behind.
  const shown = Math.min(active ?? configuredIndex, points.length - 1)
  const current = points[shown]
  const cheapest = points.reduce((best, p) => (p.y < best.y ? p : best), points[0])

  function onPointer(event: PointerEvent<SVGRectElement>): void {
    const box = event.currentTarget.ownerSVGElement?.getBoundingClientRect()
    if (!box || box.width === 0) return
    const svgX = ((event.clientX - box.left) / box.width) * W
    const value = xMin + ((svgX - M.left) / (W - M.left - M.right)) * (xMax - xMin)
    setActive(nearestIndex(points, value))
  }

  function onKey(event: KeyboardEvent<HTMLDivElement>): void {
    const last = points.length - 1
    if (event.key === 'Escape') {
      setActive(null)
      return
    }
    const next = { ArrowRight: shown + 1, ArrowLeft: shown - 1, Home: 0, End: last }[event.key]
    if (next === undefined) return
    event.preventDefault()
    setActive(Math.min(last, Math.max(0, next)))
  }

  const tipLeft = (x(current.x) / W) * 100
  return (
    <figure className="viz" aria-labelledby={`${id}-cap`}>
      <figcaption id={`${id}-cap`} className="viz-title">{title}</figcaption>
      <ul className="viz-legend" aria-label="Legend">
        <li><span className="viz-key viz-key-line" aria-hidden="true" />Total cost when auto-approving above the threshold</li>
        <li><span className="viz-key viz-key-ref" aria-hidden="true" />Never auto-approve (everyone to a person)</li>
      </ul>
      <p className="sr-only">
        Line chart, {points.length} thresholds from {points[0].x.toFixed(2)} to {points[points.length - 1].x.toFixed(2)}.
        Lowest cost {cheapest.y} at {cheapest.x.toFixed(2)}; never auto-approving costs {baseline}; configured threshold {configured}.
      </p>
      <div
        className="viz-frame"
        tabIndex={0}
        role="slider"
        aria-roledescription="chart"
        aria-label={`${title}. Arrow keys step through thresholds.`}
        aria-valuemin={0}
        aria-valuemax={points.length - 1}
        aria-valuenow={shown}
        aria-valuetext={`Threshold ${current.x.toFixed(2)}, cost ${current.y}, ${current.wrong} wrong approvals, ${current.delayed} delayed`}
        onKeyDown={onKey}
      >
        <svg viewBox={`0 0 ${W} ${H}`} className="viz-svg" aria-hidden="true" focusable="false">
          {yTicks.map((t) => (
            <g key={`y${t}`}>
              <line className="viz-grid" x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} />
              <text className="viz-tick" x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end">{t}</text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={`x${t}`} className="viz-tick" x={x(t)} y={H - M.bottom + 18} textAnchor="middle">{t.toFixed(2)}</text>
          ))}
          <text className="viz-axis-label" x={(M.left + W - M.right) / 2} y={H - 6} textAnchor="middle">Auto-approval threshold (confidence)</text>
          <text className="viz-axis-label" x={14} y={M.top - 6}>Cost</text>
          <line className="viz-baseline" x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} />

          <line className="viz-ref" x1={M.left} x2={W - M.right} y1={y(baseline)} y2={y(baseline)} />
          <text className="viz-ref-label" x={M.left + 6} y={y(baseline) - 6}>Never auto-approve: {baseline}</text>

          <line className="viz-marker" x1={x(configured)} x2={x(configured)} y1={M.top} y2={H - M.bottom} />
          <text className="viz-marker-label" x={x(configured) - 6} y={H - M.bottom - 8} textAnchor="end">Configured {configured}</text>

          <path className="viz-line" d={path} />
          {active !== null && <line className="viz-crosshair" x1={x(current.x)} x2={x(current.x)} y1={M.top} y2={H - M.bottom} />}
          <circle className="viz-dot" cx={x(current.x)} cy={y(current.y)} r={5} />
          <rect
            className="viz-hit"
            x={M.left}
            y={M.top}
            width={W - M.left - M.right}
            height={H - M.top - M.bottom}
            style={{ touchAction: 'pan-y' }}
            onPointerDown={onPointer}
            onPointerMove={onPointer}
            onPointerLeave={(e) => e.pointerType === 'mouse' && setActive(null)}
          />
        </svg>
        {active !== null && (
          <div className="viz-tip" style={{ left: `${tipLeft}%` }} aria-hidden="true">
            <strong>Cost {current.y}</strong>
            <span>threshold {current.x.toFixed(2)}</span>
            <span>{current.wrong} wrong approvals, {current.delayed} delayed</span>
          </div>
        )}
      </div>
      <p className="viz-readout">
        At threshold <strong>{current.x.toFixed(2)}</strong>: total cost <strong>{current.y}</strong> ({current.wrong} wrong
        approvals x 20 + {current.delayed} delayed genuine claims x 1), {pct(current.autoRate)} auto-approved.
      </p>
      <TableView caption={`${title} (table)`} head={['Threshold', 'Total cost', 'Wrong approvals', 'Delayed genuine', 'Auto-approved']}
        rows={points.map((p) => [p.x.toFixed(2), String(p.y), String(p.wrong), String(p.delayed), pct(p.autoRate)])} />
    </figure>
  )
}

interface BarChartProps {
  bars: Bar[]
  title: string
  max?: number
  valueHeader?: string
}

const BAR_W = 300
const BAR_H = 20

/** Horizontal bars, one series. The bar is the hit target; hover or focus shows the detail. */
export function BarChart({ bars, title, max, valueHeader = 'Value' }: BarChartProps) {
  const id = useId()
  const [active, setActive] = useState<string | null>(null)
  const top = max ?? Math.max(...bars.map((b) => b.value), 1)
  if (bars.length === 0) return <p className="muted">Nothing to show in this run.</p>
  return (
    <figure className="viz" aria-labelledby={`${id}-cap`}>
      <figcaption id={`${id}-cap`} className="viz-title">{title}</figcaption>
      <ul className="viz-bars">
        {bars.map((b) => {
          const width = top > 0 ? Math.max(0, Math.min(1, b.value / top)) * BAR_W : 0
          const r = Math.min(4, width / 2)
          const d = width > 0
            ? `M0,0 H${width - r} Q${width},0 ${width},${r} V${BAR_H - r} Q${width},${BAR_H} ${width - r},${BAR_H} H0 Z`
            : ''
          return (
            <li
              key={b.key}
              className={active === b.key ? 'viz-bar-row is-active' : 'viz-bar-row'}
              onPointerEnter={() => setActive(b.key)}
              onPointerLeave={() => setActive(null)}
            >
              <span className="viz-bar-label">{b.label}{b.detail && <span className="sr-only">, {b.detail}</span>}</span>
              <span className="viz-bar-track">
                <svg viewBox={`0 0 ${BAR_W} ${BAR_H}`} preserveAspectRatio="none" className="viz-bar-svg" aria-hidden="true" focusable="false">
                  <line className="viz-baseline" x1={0.5} x2={0.5} y1={0} y2={BAR_H} />
                  {d && <path className="viz-bar" d={d} />}
                </svg>
                {active === b.key && b.detail && <span className="viz-tip viz-tip-bar" aria-hidden="true"><strong>{b.display}</strong><span>{b.detail}</span></span>}
              </span>
              <span className="viz-bar-value">{b.display}</span>
            </li>
          )
        })}
      </ul>
      <TableView caption={`${title} (table)`} head={['Item', valueHeader, 'Detail']} rows={bars.map((b) => [b.label, b.display, b.detail ?? ''])} />
    </figure>
  )
}

interface TableViewProps {
  caption: string
  head: string[]
  rows: string[][]
}

/** The table view behind every chart: every value is reachable without hovering. */
export function TableView({ caption, head, rows }: TableViewProps) {
  return (
    <details className="viz-table">
      <summary>Show as table<span className="sr-only">: {caption}</span></summary>
      <div className="table-wrap">
        <table className="table table-dense">
          <caption className="sr-only">{caption}</caption>
          <thead><tr>{head.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
          <tbody>
            {rows.map((r, rowIndex) => (
              <tr key={rowIndex}>{r.map((c, i) => (i === 0 ? <th key={i} scope="row">{c}</th> : <td key={i} className="num">{c}</td>))}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
