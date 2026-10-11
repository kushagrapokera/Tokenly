/**
 * Legend for the chart series.
 *
 * Recharts' own `Legend` measures its box to shrink the plot area, which collapses the
 * chart to nothing when the container cannot be measured. Rendering the legend here
 * instead keeps the chart purely about geometry: the swatches use the same design
 * tokens as the series, and the labels are real text a screen reader can read.
 */

import { formatInteger } from '../../lib/format'

export interface LegendEntry {
  key: string
  label: string
  color: string
  /** The current value for this series, shown next to the label. */
  value?: number
}

export function ChartLegend({ entries }: { entries: LegendEntry[] }) {
  if (entries.length === 0) {
    return null
  }
  return (
    <ul className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1">
      {entries.map((entry) => (
        <li key={entry.key} className="flex items-center gap-1.5 text-xs">
          <span
            aria-hidden="true"
            className="inline-block size-2.5 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-[var(--color-ink-muted)]">{entry.label}</span>
          {entry.value !== undefined ? (
            <span className="tabular font-medium text-[var(--color-ink)]">
              {formatInteger(entry.value)}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  )
}
