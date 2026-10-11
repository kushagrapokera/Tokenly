/**
 * Tracking status panel.
 *
 * This is the panel that tells the user whether the numbers above it can be trusted.
 * It shows OpenCode detection, the last successful sync, how many events are stored,
 * and — importantly — an explicit warning when some records carried no token totals.
 * An unavailable collector is reported as a normal state, not an error, because not
 * having OpenCode installed is a legitimate way to run the dashboard.
 */

import { useState } from 'react'

import { fetchCollectorStatus, triggerRescan } from '../api/client'
import type { CollectorStatusEntry, CollectorStatusResponse } from '../api/types'
import { useAsyncData } from '../hooks/useAsyncData'
import { formatCount, formatRelative, formatTimestamp } from '../lib/format'
import { Badge, Panel, StateMessage } from './ui'

export function TrackingStatusPanel() {
  const { state, reload } = useAsyncData<CollectorStatusResponse>(
    () => fetchCollectorStatus(),
    [],
  )
  const [rescanning, setRescanning] = useState(false)
  const [rescanNote, setRescanNote] = useState<string | null>(null)

  async function rescan() {
    setRescanning(true)
    setRescanNote(null)
    try {
      const runs = await triggerRescan()
      const inserted = runs.reduce((total, run) => total + run.inserted, 0)
      const failed = runs.filter((run) => !run.succeeded)
      setRescanNote(
        failed.length > 0
          ? `Rescan finished with ${formatCount(failed.length, 'failure')}: ${failed[0]?.error_message ?? 'unknown error'}`
          : `Rescan complete — ${formatCount(inserted, 'new record')} stored.`,
      )
      reload()
    } catch (error) {
      setRescanNote(error instanceof Error ? error.message : 'Rescan failed.')
    } finally {
      setRescanning(false)
    }
  }

  return (
    <Panel
      title="Tracking status"
      subtitle="Whether usage is being collected, and how much is stored"
      action={
        <button
          type="button"
          onClick={rescan}
          disabled={rescanning}
          className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--color-surface-raised)] focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:outline-none disabled:opacity-50"
        >
          {rescanning ? 'Rescanning…' : 'Rescan now'}
        </button>
      }
    >
      {state.status === 'loading' ? <StateMessage kind="loading" /> : null}

      {state.status === 'error' ? (
        <StateMessage kind="error" message={state.error.message} onRetry={reload} />
      ) : null}

      {rescanNote ? (
        <p role="status" className="mb-3 text-xs text-[var(--color-ink-muted)]">
          {rescanNote}
        </p>
      ) : null}

      {state.status === 'ready' && state.data.collectors.length === 0 ? (
        <StateMessage kind="empty" message="No collectors are configured." />
      ) : null}

      {state.status === 'ready'
        ? state.data.collectors.map((collector) => (
            <CollectorRow key={collector.platform} collector={collector} />
          ))
        : null}
    </Panel>
  )
}

function CollectorRow({ collector }: { collector: CollectorStatusEntry }) {
  return (
    <div className="border-t border-[var(--color-border)]/60 py-3 first:border-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-medium capitalize">{collector.platform}</h3>
        <StatusBadge collector={collector} />
      </div>

      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-[var(--color-ink-muted)]">OpenCode</dt>
          <dd>{collector.available ? 'Detected' : 'Not found'}</dd>
        </div>
        <div>
          <dt className="text-[var(--color-ink-muted)]">Last sync</dt>
          <dd title={formatTimestamp(collector.last_scan_at)}>
            {formatRelative(collector.last_scan_at)}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--color-ink-muted)]">Imported</dt>
          <dd className="tabular">{formatCount(collector.stored_events, 'event')}</dd>
        </div>
      </dl>

      {collector.detail ? (
        <p className="mt-2 break-words text-xs text-[var(--color-ink-muted)]">
          {collector.detail}
        </p>
      ) : null}

      {collector.status === 'error' ? (
        <p className="mt-2 text-xs text-[var(--color-danger)]">
          The last scan failed. Stored usage is unaffected — run a rescan to retry.
        </p>
      ) : null}

      {collector.status === 'scanning' ? (
        <p className="mt-2 text-xs text-[var(--color-warning)]">
          A scan is in progress; totals may still be rising.
        </p>
      ) : null}
    </div>
  )
}

function StatusBadge({ collector }: { collector: CollectorStatusEntry }) {
  if (!collector.available) {
    return <Badge tone="neutral">Not detected</Badge>
  }
  const tones: Record<CollectorStatusEntry['status'], 'positive' | 'warning' | 'danger' | 'neutral'> =
    {
      idle: 'positive',
      scanning: 'warning',
      error: 'danger',
      never_scanned: 'neutral',
    }
  const labels: Record<CollectorStatusEntry['status'], string> = {
    idle: 'Tracking active',
    scanning: 'Scanning',
    error: 'Sync failed',
    never_scanned: 'Never synced',
  }
  return <Badge tone={tones[collector.status]}>{labels[collector.status]}</Badge>
}
