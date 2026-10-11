/**
 * Date-range, platform, provider, and model filters.
 *
 * The platform, provider, and model options are derived from the unfiltered model
 * breakdown rather than hard-coded, so a newly used model — or a newly added
 * assistant — appears without a frontend change. That list is fetched once and
 * never filtered by itself; otherwise selecting one provider would remove the
 * others from the dropdown and make switching back impossible.
 */

import { useEffect, useState } from 'react'

import { fetchModels } from '../api/client'
import type { ModelBreakdownResponse, RangeName } from '../api/types'
import { DEFAULT_FILTERS, RANGE_OPTIONS, platformLabel } from './filterState'
import type { DashboardFilters } from './filterState'

export function FilterBar({
  filters,
  onChange,
  timezone,
}: {
  filters: DashboardFilters
  onChange: (next: DashboardFilters) => void
  timezone: string
}) {
  const [options, setOptions] = useState<ModelBreakdownResponse['models']>([])

  useEffect(() => {
    let cancelled = false
    fetchModels({ range: 'all_time', timezone })
      .then((breakdown) => {
        if (!cancelled) {
          setOptions(breakdown.models)
        }
      })
      .catch(() => {
        // The option lists are a convenience; if they cannot load, the rest of the page
        // still works and the dropdowns simply stay empty.
        if (!cancelled) {
          setOptions([])
        }
      })
    return () => {
      cancelled = true
    }
  }, [timezone])

  const platforms = distinct(options.map((model) => model.platform))
  const providers = distinct(options.map((model) => model.provider_id))
  const models = distinct(options.map((model) => model.model_id))

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <Select
        id="range"
        label="Date range"
        value={filters.range}
        onChange={(value) => onChange({ ...filters, range: value as RangeName })}
        options={RANGE_OPTIONS.map((option) => ({ value: option.value, label: option.label }))}
      />

      {filters.range === 'custom' ? (
        <>
          <DateInput
            id="start"
            label="From"
            value={filters.start}
            onChange={(start) => onChange({ ...filters, start })}
          />
          <DateInput
            id="end"
            label="To"
            value={filters.end}
            onChange={(end) => onChange({ ...filters, end })}
          />
        </>
      ) : null}

      <Select
        id="platform"
        label="Platform"
        value={filters.platform ?? ''}
        onChange={(platform) => onChange({ ...filters, platform: platform || null })}
        options={[
          { value: '', label: 'All platforms' },
          ...platforms.map((platform) => ({ value: platform, label: platformLabel(platform) })),
        ]}
      />

      <Select
        id="provider"
        label="Provider"
        value={filters.provider ?? ''}
        onChange={(provider) => onChange({ ...filters, provider: provider || null })}
        options={[
          { value: '', label: 'All providers' },
          ...providers.map((provider) => ({ value: provider, label: provider })),
        ]}
      />

      <Select
        id="model"
        label="Model"
        value={filters.model ?? ''}
        onChange={(model) => onChange({ ...filters, model: model || null })}
        options={[
          { value: '', label: 'All models' },
          ...models.map((model) => ({ value: model, label: model })),
        ]}
      />

      <button
        type="button"
        onClick={() => onChange(DEFAULT_FILTERS)}
        className="ml-auto rounded-md border border-[var(--color-border)] px-3 py-2 text-xs font-medium text-[var(--color-ink-muted)] transition-colors hover:bg-[var(--color-surface-raised)] focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:outline-none"
      >
        Reset
      </button>
    </div>
  )
}

function Select({
  id,
  label,
  value,
  onChange,
  options,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-[var(--color-ink-muted)]">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:outline-none"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}

function DateInput({
  id,
  label,
  value,
  onChange,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-[var(--color-ink-muted)]">
        {label}
      </label>
      <input
        id={id}
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:outline-none"
      />
    </div>
  )
}

function distinct(values: string[]): string[] {
  return [...new Set(values)].sort((left, right) => left.localeCompare(right))
}
