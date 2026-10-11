/**
 * Usage charts over the selected range.
 *
 * The three calendar series and the input/output split are fetched from one place so
 * the panels below the table always agree with each other: each chart states its
 * granularity explicitly rather than inheriting whatever the last request returned.
 *
 * Once loaded, each chart also names the window it actually covers. The range filter
 * defaults to the last seven days, so a chart that does not say so can be read as the
 * whole history; the model breakdown below already stated its window, and these
 * panels now match it.
 */

import { fetchDaily, fetchMonthly, fetchTimeline, fetchYearly } from '../api/client'
import type { TimelineResponse } from '../api/types'
import { useAsyncData } from '../hooks/useAsyncData'
import { InputOutputChart } from './charts/InputOutputChart'
import { TimelineChart } from './charts/TimelineChart'
import { Panel, StateMessage } from './ui'
import type { DashboardFilters } from './filterState'

function queryFor(filters: DashboardFilters, timezone: string) {
  return {
    range: filters.range,
    timezone,
    start: filters.start,
    end: filters.end,
    platform: filters.platform,
    provider_id: filters.provider,
    model_id: filters.model,
  }
}

export function UsageCharts({
  filters,
  timezone,
}: {
  filters: DashboardFilters
  timezone: string
}) {
  const query = queryFor(filters, timezone)

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <TimelinePanel
        title="Daily usage"
        subtitle="Tokens per calendar day"
        load={() => fetchDaily(query)}
        kind="daily"
        filters={filters}
        timezone={timezone}
      />
      <TimelinePanel
        title="Monthly usage"
        subtitle="Tokens per calendar month"
        load={() => fetchMonthly(query)}
        kind="monthly"
        filters={filters}
        timezone={timezone}
      />
      <TimelinePanel
        title="Yearly usage"
        subtitle="Tokens per calendar year"
        load={() => fetchYearly(query)}
        kind="yearly"
        filters={filters}
        timezone={timezone}
      />
      <TimelinePanel
        title="Input vs output"
        subtitle="How each period's tokens split"
        load={() => fetchTimeline(query, 'day')}
        kind="daily"
        split
        filters={filters}
        timezone={timezone}
      />
    </div>
  )
}

function TimelinePanel({
  title,
  subtitle,
  load,
  kind,
  split,
  filters,
  timezone,
}: {
  title: string
  subtitle: string
  load: () => Promise<TimelineResponse>
  kind: 'daily' | 'monthly' | 'yearly'
  split?: boolean
  filters: DashboardFilters
  timezone: string
}) {
  const { state, reload } = useAsyncData<TimelineResponse>(load, [filters, timezone])

  return (
    <Panel
      title={title}
      subtitle={state.status === 'ready' ? `${subtitle} · ${describeWindow(state.data.window.label)}` : subtitle}
    >
      {state.status === 'loading' ? <StateMessage kind="loading" /> : null}
      {state.status === 'error' ? (
        <StateMessage kind="error" message={state.error.message} onRetry={reload} />
      ) : null}
      {state.status === 'ready' ? (
        split ? (
          <InputOutputChart timeline={state.data} />
        ) : (
          <TimelineChart timeline={state.data} kind={kind} />
        )
      ) : null}
    </Panel>
  )
}

function describeWindow(label: string): string {
  return label.replace(/_/g, ' ')
}
