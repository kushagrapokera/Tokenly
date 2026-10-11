/**
 * The Tokenly dashboard.
 *
 * The page is organised as: a headline row that never changes with the filters, then
 * the filter bar, then everything that responds to it. That ordering is deliberate —
 * the headline cards answer "how much have I used" and should not shift under the user
 * while they are comparing ranges.
 */

import { useState } from 'react'

import { ModelBreakdownTable } from './components/ModelBreakdownTable'
import { ModelComparisonPanel } from './components/ModelComparisonPanel'
import { MetricsCards } from './components/MetricsCards'
import { TrackingStatusPanel } from './components/TrackingStatusPanel'
import { UsageCharts } from './components/UsageCharts'
import { FilterBar } from './components/filters'
import { DEFAULT_FILTERS } from './components/filterState'
import type { DashboardFilters } from './components/filterState'

/**
 * The timezone every request is built in.
 *
 * The backend defaults to UTC when this is absent, which would put "today" on the wrong
 * day for most of the world. Sending the browser's own zone means the dashboard's idea
 * of today is the user's.
 */
const TIMEZONE = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'

export function App() {
  const [filters, setFilters] = useState<DashboardFilters>(DEFAULT_FILTERS)

  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-5 p-4 sm:p-6 lg:p-8">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Tokenly</h1>
          <p className="mt-0.5 text-sm text-[var(--color-ink-muted)]">
            OpenCode token usage, collected locally
          </p>
        </div>
        <p className="text-xs text-[var(--color-ink-muted)]">Times shown in {TIMEZONE}</p>
      </header>

      <MetricsCards timezone={TIMEZONE} />

      <FilterBar filters={filters} onChange={setFilters} timezone={TIMEZONE} />

      <UsageCharts filters={filters} timezone={TIMEZONE} />

      <ModelComparisonPanel timezone={TIMEZONE} />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ModelBreakdownTable filters={filters} timezone={TIMEZONE} />
        </div>
        <TrackingStatusPanel />
      </div>

      <footer className="mt-auto pt-2 text-center text-xs text-[var(--color-ink-muted)]">
        Read-only local tracker — your OpenCode data never leaves this machine.
      </footer>
    </div>
  )
}

export default App
