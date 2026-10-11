/**
 * Formatting numbers for display.
 *
 * Token counts run into the hundreds of millions, so exact digits are unreadable on a
 * card. These helpers keep the precision decisions in one place: a headline number is
 * abbreviated, a table cell keeps what it can, and anything under a thousand is shown
 * exactly.
 */

const COMPACT_UNITS = [
  { limit: 1_000_000_000, suffix: 'B' },
  { limit: 1_000_000, suffix: 'M' },
  { limit: 1_000, suffix: 'K' },
] as const

/**
 * Abbreviate a token count for a headline: `1,234,567` becomes `1.23M`.
 *
 * Values below a thousand are shown exactly, because rounding a small number to `0K`
 * would turn real usage into an apparent absence.
 */
export function formatCompact(value: number): string {
  if (!Number.isFinite(value)) {
    return '—'
  }
  const magnitude = Math.abs(value)
  for (const { limit, suffix } of COMPACT_UNITS) {
    if (magnitude >= limit) {
      const scaled = value / limit
      return `${trimZeroes(scaled.toFixed(2))}${suffix}`
    }
  }
  return formatInteger(value)
}

/** Group a number with thousands separators, keeping every digit. */
export function formatInteger(value: number): string {
  if (!Number.isFinite(value)) {
    return '—'
  }
  return new Intl.NumberFormat('en-US').format(value)
}

/** Show an exact count with a unit word: `1,234 requests`. */
export function formatCount(value: number, noun: string, plural?: string): string {
  const word = value === 1 ? noun : (plural ?? `${noun}s`)
  return `${formatInteger(value)} ${word}`
}

/** Format a timestamp as a local date and time, or a dash when absent. */
export function formatTimestamp(value: string | null): string {
  if (!value) {
    return '—'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return '—'
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed)
}

/** Format a timestamp as "how long ago", falling back to an absolute date past a week. */
export function formatRelative(value: string | null, now: Date = new Date()): string {
  if (!value) {
    return 'never'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return 'never'
  }
  const seconds = Math.round((now.getTime() - parsed.getTime()) / 1000)
  if (seconds < 0) {
    return 'just now'
  }
  if (seconds < 60) {
    return 'just now'
  }
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)} min ago`
  }
  if (seconds < 86400) {
    return `${Math.floor(seconds / 3600)} h ago`
  }
  if (seconds < 604800) {
    return `${Math.floor(seconds / 86400)} d ago`
  }
  return formatTimestamp(value)
}

/** Format a duration in seconds as a short human phrase. */
export function formatDuration(seconds: number): string {
  if (seconds < 1) {
    return `${Math.round(seconds * 1000)}ms`
  }
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`
  }
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
}

/**
 * Render a bucket label for a chart axis.
 *
 * `2026-10-11` is too wide for a day axis and `2026-10` is too terse for a tooltip,
 * so each granularity gets its own presentation and the full label stays in the title.
 */
export function formatBucketLabel(label: string, granularity: string): string {
  if (granularity === 'day') {
    return label.slice(5)
  }
  return label
}

function trimZeroes(text: string): string {
  return text.replace(/\.?0+$/, '')
}
