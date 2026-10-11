import { describe, expect, it } from 'vitest'

import {
  formatBucketLabel,
  formatCompact,
  formatCount,
  formatDuration,
  formatInteger,
  formatRelative,
  formatTimestamp,
} from './format'

describe('formatCompact', () => {
  it('abbreviates thousands, millions, and billions', () => {
    expect(formatCompact(1_500)).toBe('1.5K')
    expect(formatCompact(2_400_000)).toBe('2.4M')
    expect(formatCompact(3_100_000_000)).toBe('3.1B')
  })

  it('shows small numbers exactly rather than rounding them to zero', () => {
    expect(formatCompact(0)).toBe('0')
    expect(formatCompact(999)).toBe('999')
  })

  it('drops trailing zeroes so 1.20M reads as 1.2M', () => {
    expect(formatCompact(1_200_000)).toBe('1.2M')
  })

  it('marks a non-finite value rather than printing NaN', () => {
    expect(formatCompact(Number.NaN)).toBe('—')
  })
})

describe('formatInteger', () => {
  it('groups thousands', () => {
    expect(formatInteger(1_234_567)).toBe('1,234,567')
  })
})

describe('formatCount', () => {
  it('uses the singular for exactly one', () => {
    expect(formatCount(1, 'request')).toBe('1 request')
  })

  it('pluralizes everything else', () => {
    expect(formatCount(0, 'request')).toBe('0 requests')
    expect(formatCount(2, 'request')).toBe('2 requests')
  })

  it('accepts an irregular plural', () => {
    expect(formatCount(3, 'query', 'queries')).toBe('3 queries')
  })
})

describe('formatTimestamp', () => {
  it('formats an ISO timestamp', () => {
    expect(formatTimestamp('2026-10-11T11:49:09Z')).toMatch(/2026/)
  })

  it('shows a dash for a missing or unparseable value', () => {
    expect(formatTimestamp(null)).toBe('—')
    expect(formatTimestamp('not a date')).toBe('—')
  })
})

describe('formatRelative', () => {
  const now = new Date('2026-10-11T12:00:00Z')

  it('describes recent moments in short units', () => {
    expect(formatRelative('2026-10-11T11:59:30Z', now)).toBe('just now')
    expect(formatRelative('2026-10-11T11:30:00Z', now)).toBe('30 min ago')
    expect(formatRelative('2026-10-11T09:00:00Z', now)).toBe('3 h ago')
    expect(formatRelative('2026-10-09T12:00:00Z', now)).toBe('2 d ago')
  })

  it('says never when there is no timestamp', () => {
    expect(formatRelative(null, now)).toBe('never')
  })

  it('falls back to an absolute date beyond a week', () => {
    expect(formatRelative('2026-09-01T12:00:00Z', now)).toMatch(/2026/)
  })

  it('does not report a future timestamp as negative time', () => {
    expect(formatRelative('2026-10-11T12:30:00Z', now)).toBe('just now')
  })
})

describe('formatDuration', () => {
  it('switches units at sensible thresholds', () => {
    expect(formatDuration(0.25)).toBe('250ms')
    expect(formatDuration(1.5)).toBe('1.5s')
    expect(formatDuration(90)).toBe('1m 30s')
  })
})

describe('formatBucketLabel', () => {
  it('shortens day labels to month-day for a crowded axis', () => {
    expect(formatBucketLabel('2026-10-11', 'day')).toBe('10-11')
  })

  it('leaves month and year labels whole', () => {
    expect(formatBucketLabel('2026-10', 'month')).toBe('2026-10')
    expect(formatBucketLabel('2026', 'year')).toBe('2026')
  })
})
