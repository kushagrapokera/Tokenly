/**
 * The headline cards the dashboard opens with.
 *
 * Which cards exist is declared here, apart from the component that renders them, so
 * adding a period is a one-line change and the card component stays about presentation.
 */

import type { RangeName } from '../api/types'

export interface MetricCardSpec {
  key: string
  label: string
  range: RangeName
  hint: string
}

export const METRIC_CARDS: MetricCardSpec[] = [
  { key: 'today', label: 'Today', range: 'today', hint: 'Since midnight' },
  { key: 'month', label: 'This month', range: 'current_month', hint: 'Calendar month' },
  { key: 'year', label: 'This year', range: 'current_year', hint: 'Calendar year' },
  { key: 'all', label: 'All time', range: 'all_time', hint: 'Everything stored' },
]
