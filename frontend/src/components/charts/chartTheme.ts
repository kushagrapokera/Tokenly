/**
 * Recharts configuration shared by every chart.
 *
 * Colours are read from the CSS variables in `index.css` rather than hard-coded here,
 * so the charts follow the light/dark theme without a second palette living in
 * JavaScript. The formatters widen their parameter type because Recharts hands a
 * possibly-undefined value to a tick formatter.
 */

import { formatCompact, formatInteger } from '../../lib/format'

export function token(name: string): string {
  if (typeof window === 'undefined') {
    return `var(--color-${name})`
  }
  const value = window
    .getComputedStyle(document.documentElement)
    .getPropertyValue(`--color-${name}`)
  return value.trim() || `var(--color-${name})`
}

export function axisProps() {
  return {
    stroke: token('border'),
    tick: { fill: token('ink-muted'), fontSize: 11 },
    tickLine: false,
    axisLine: false,
  } as const
}

export function gridProps() {
  return {
    stroke: token('border'),
    strokeDasharray: '3 3',
    vertical: false,
  } as const
}

export function tooltipProps() {
  return {
    cursor: { fill: token('surface-sunken'), opacity: 0.6 },
    contentStyle: {
      background: token('surface-raised'),
      border: `1px solid ${token('border')}`,
      borderRadius: 8,
      fontSize: 12,
      color: token('ink'),
    },
    labelStyle: { color: token('ink'), fontWeight: 600 },
  } as const
}

/** Format a Y-axis tick compactly, so 9,543,922 reads as `9.54M`. */
export function compactTick(value: unknown): string {
  return typeof value === 'number' ? formatCompact(value) : ''
}

/** Format a tooltip value, which may arrive as a string when series are stacked. */
export function integerValue(value: unknown): string {
  return typeof value === 'number' ? formatInteger(value) : String(value ?? '')
}
