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
