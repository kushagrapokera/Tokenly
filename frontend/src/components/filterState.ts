/**
 * The filters the dashboard applies to every panel below the headline cards.
 *
 * Declared in its own module so both the filter bar and the panels that consume the
 * values agree on one shape, and so a default can change in exactly one place.
 */

import type { RangeName } from '../api/types'

export interface DashboardFilters {
  range: RangeName
  start: string
  end: string
  platform: string | null
  provider: string | null
  model: string | null
}

export const DEFAULT_FILTERS: DashboardFilters = {
  range: 'last_7_days',
  start: '',
  end: '',
  platform: null,
  provider: null,
  model: null,
}

/**
 * Display names for platform identifiers.
 *
 * The stored id is lowercase and stable (`opencode`, `cline`); these are only for
 * showing it. Kept here rather than re-derived per panel, so the filter dropdown,
 * the breakdown table, and the tracking panel cannot disagree about how a
 * platform is spelled. An unknown id falls back to itself, so a newly added
 * assistant renders correctly before this map is updated.
 */
export const PLATFORM_LABELS: Record<string, string> = {
  opencode: 'OpenCode',
  cline: 'Cline',
}

/**
 * The display name for a platform id, falling back to the id itself.
 *
 * One function so the filter dropdown, the breakdown table, and the tracking
 * panel cannot drift apart in how they name the same platform.
 */
export function platformLabel(platformId: string): string {
  return PLATFORM_LABELS[platformId] ?? platformId
}

export const RANGE_OPTIONS: { value: RangeName; label: string }[] = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'current_month', label: 'This month' },
  { value: 'previous_month', label: 'Last month' },
  { value: 'current_year', label: 'This year' },
  { value: 'all_time', label: 'All time' },
  { value: 'custom', label: 'Custom range' },
]
