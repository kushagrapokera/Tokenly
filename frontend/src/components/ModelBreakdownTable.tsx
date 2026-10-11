/**
 * Model-wise usage table.
 *
 * Rows keep provider and model as separate columns because two providers can serve the
 * same model name, and collapsing them would attribute one provider's usage to
 * another. The per-row unknown count is shown for the same reason the summary shows
 * completeness: a total that silently excludes unknown records reads as exact.
 */

import { fetchModels } from '../api/client'
import type { ModelBreakdownResponse } from '../api/types'
import { useAsyncData } from '../hooks/useAsyncData'
import { formatCompact, formatCount, formatInteger } from '../lib/format'
import { Panel, StateMessage } from './ui'
import type { DashboardFilters } from './filterState'

export function ModelBreakdownTable({
  filters,
  timezone,
}: {
  filters: DashboardFilters
  timezone: string
}) {
  const { state, reload } = useAsyncData<ModelBreakdownResponse>(
    () =>
      fetchModels({
        range: filters.range,
        timezone,
        start: filters.start,
        end: filters.end,
        platform: filters.platform,
        provider_id: filters.provider,
        model_id: filters.model,
      }),
    [filters, timezone],
  )

  return (
    <Panel
      title="Model breakdown"
      subtitle={state.status === 'ready' ? describeScope(state.data.window.label) : undefined}
    >
      {state.status === 'loading' ? <StateMessage kind="loading" /> : null}

      {state.status === 'error' ? (
        <StateMessage kind="error" message={state.error.message} onRetry={reload} />
      ) : null}

      {state.status === 'ready' && state.data.models.length === 0 ? (
        <StateMessage kind="empty" message="No models match the current filters." />
      ) : null}

      {state.status === 'ready' && state.data.models.length > 0 ? (
        <ModelTable models={state.data.models} />
      ) : null}
    </Panel>
  )
}

function ModelTable({ models }: { models: ModelBreakdownResponse['models'] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)] text-left text-xs tracking-wide text-[var(--color-ink-muted)] uppercase">
            <th scope="col" className="py-2 pr-4 font-medium">
              Model
            </th>
            <th scope="col" className="py-2 pr-4 font-medium">
              Provider
            </th>
            <th scope="col" className="py-2 pr-4 text-right font-medium">
              Input
            </th>
            <th scope="col" className="py-2 pr-4 text-right font-medium">
              Output
            </th>
            <th scope="col" className="py-2 pr-4 text-right font-medium">
              Total
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              Requests
            </th>
          </tr>
        </thead>
        <tbody>
          {models.map((model) => (
            <tr
              key={`${model.provider_id}:${model.model_id}`}
              className="border-b border-[var(--color-border)]/60 last:border-0"
            >
              <th scope="row" className="py-2.5 pr-4 text-left font-medium">
                <span className="block break-words">{model.model_id}</span>
                {model.unknown_total_events > 0 ? (
                  <span className="mt-0.5 block text-xs font-normal text-[var(--color-warning)]">
                    {formatCount(model.unknown_total_events, 'record')} reported no total
                  </span>
                ) : null}
              </th>
              <td className="py-2.5 pr-4 text-[var(--color-ink-muted)]">
                <span className="break-words">{model.provider_id}</span>
              </td>
              <td className="tabular py-2.5 pr-4 text-right">
                {formatInteger(model.totals.input_tokens)}
              </td>
              <td className="tabular py-2.5 pr-4 text-right">
                {formatInteger(model.totals.output_tokens)}
              </td>
              <td className="tabular py-2.5 pr-4 text-right font-medium">
                {formatCompact(model.totals.total_tokens)}
              </td>
              <td className="tabular py-2.5 text-right">{formatInteger(model.request_count)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function describeScope(label: string): string {
  return `Totals for ${label.replace(/_/g, ' ')}`
}
