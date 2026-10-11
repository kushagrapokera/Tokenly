/**
 * Headline cards: tokens today, this month, this year, and all time.
 *
 * Each card is one summary request. They are fetched together rather than in sequence
 * so the page settles in one pass — four cards appearing one at a time reads as four
 * separate loads.
 *
 * The cards honour the same filters as every panel below them. They previously took
 * only a timezone, which meant narrowing to one platform changed the charts but left
 * the headline totals showing every platform — the numbers you look at first were the
 * ones ignoring the filter.
 */

import { fetchSummary } from '../api/client'
import type { SummaryResponse } from '../api/types'
import { useAsyncData } from '../hooks/useAsyncData'
import { formatCompact, formatCount, formatInteger } from '../lib/format'
import { METRIC_CARDS } from './metricCards'
import type { MetricCardSpec } from './metricCards'
import type { DashboardFilters } from './filterState'
import { Badge, Skeleton } from './ui'

export function MetricsCards({
  filters,
  timezone,
}: {
  filters: DashboardFilters
  timezone: string
}) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {METRIC_CARDS.map((spec) => (
        <MetricCard key={spec.key} spec={spec} filters={filters} timezone={timezone} />
      ))}
    </div>
  )
}

function MetricCard({
  spec,
  filters,
  timezone,
}: {
  spec: MetricCardSpec
  filters: DashboardFilters
  timezone: string
}) {
  const { state } = useAsyncData<SummaryResponse>(
    () =>
      fetchSummary({
        range: spec.range,
        timezone,
        platform: filters.platform,
        provider_id: filters.provider,
        model_id: filters.model,
      }),
    [spec.range, filters, timezone],
  )

  if (state.status === 'loading') {
    return (
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="mt-4 h-8 w-28" />
        <Skeleton className="mt-3 h-3 w-24" />
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="rounded-xl border border-[var(--color-danger)]/40 bg-[var(--color-surface)] p-5">
        <p className="text-xs font-medium text-[var(--color-ink-muted)]">{spec.label}</p>
        <p role="alert" className="mt-3 text-sm text-[var(--color-danger)]">
          {state.error.message}
        </p>
      </div>
    )
  }

  const { totals, completeness } = state.data
  const hasUsage = completeness.request_count > 0

  return (
    <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-medium tracking-wide text-[var(--color-ink-muted)] uppercase">
          {spec.label}
        </h3>
        {!completeness.is_complete ? (
          <Badge tone="warning" title="Some records reported no token totals">
            Partial
          </Badge>
        ) : null}
      </div>

      <p className="tabular mt-3 text-3xl font-semibold text-[var(--color-ink)]">
        {formatCompact(totals.total_tokens)}
      </p>
      <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
        {hasUsage ? spec.hint : 'No usage in this period'}
      </p>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1.5 border-t border-[var(--color-border)] pt-3 text-xs">
        <div>
          <dt className="text-[var(--color-ink-muted)]">Input</dt>
          <dd className="tabular font-medium">{formatInteger(totals.input_tokens)}</dd>
        </div>
        <div>
          <dt className="text-[var(--color-ink-muted)]">Output</dt>
          <dd className="tabular font-medium">{formatInteger(totals.output_tokens)}</dd>
        </div>
      </dl>

      <p className="tabular mt-3 text-[11px] text-[var(--color-ink-muted)]">
        {formatCount(completeness.request_count, 'request')}
      </p>
    </article>
  )
}
