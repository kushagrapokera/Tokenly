import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MetricsCards } from './MetricsCards'
import { ModelBreakdownTable } from './ModelBreakdownTable'
import { TrackingStatusPanel } from './TrackingStatusPanel'
import { FilterBar } from './filters'
import { DEFAULT_FILTERS } from './filterState'
import type { DashboardFilters } from './filterState'
import { makeCollectorStatus, makeModels, makeSummary, stubFetch } from '../test/fixtures'

const originalFetch = globalThis.fetch

function mockFetch(routes: Record<string, unknown>) {
  const stub = stubFetch(routes)
  globalThis.fetch = stub as unknown as typeof fetch
  return stub
}

beforeEach(() => {
  vi.stubGlobal('fetch', stubFetch({}))
})

afterEach(() => {
  globalThis.fetch = originalFetch
})

describe('MetricsCards', () => {
  it('shows a headline total for each period', async () => {
    mockFetch({ '/api/usage/summary': makeSummary() })

    render(<MetricsCards filters={DEFAULT_FILTERS} timezone="UTC" />)

    await waitFor(() => {
      expect(screen.getByText('Today')).toBeInTheDocument()
    })
    // Four cards: today, this month, this year, all time.
    expect(screen.getAllByText('1.25K')).toHaveLength(4)
  })

  it('honours the platform filter like every other panel', async () => {
    const requested: string[] = []
    const stub = stubFetch({ '/api/usage/summary': makeSummary() })
    globalThis.fetch = ((input: RequestInfo | URL) => {
      requested.push(String(input))
      return stub(input as RequestInfo)
    }) as unknown as typeof fetch

    render(
      <MetricsCards
        filters={{ ...DEFAULT_FILTERS, platform: 'cline' }}
        timezone="UTC"
      />,
    )

    await waitFor(() => {
      expect(requested.length).toBeGreaterThan(0)
    })

    // Every headline number is scoped, or the filter reads as applying only to charts.
    expect(requested.every((url) => url.includes('platform=cline'))).toBe(true)
  })

  it('reports the request count beneath the total', async () => {
    mockFetch({ '/api/usage/summary': makeSummary() })

    render(<MetricsCards filters={DEFAULT_FILTERS} timezone="UTC" />)

    expect(await screen.findAllByText('4 requests')).toHaveLength(4)
  })

  it('marks a card partial when some records reported no totals', async () => {
    mockFetch({
      '/api/usage/summary': makeSummary({
        completeness: {
          request_count: 5,
          known_total_events: 4,
          unknown_total_events: 1,
          is_complete: false,
        },
      }),
    })

    render(<MetricsCards filters={DEFAULT_FILTERS} timezone="UTC" />)

    expect(await screen.findAllByText('Partial')).toHaveLength(4)
  })

  it('says so when a period has no usage at all', async () => {
    mockFetch({
      '/api/usage/summary': makeSummary({
        totals: { input_tokens: 0, output_tokens: 0, total_tokens: 0, consumption_tokens: 0 },
        completeness: {
          request_count: 0,
          known_total_events: 0,
          unknown_total_events: 0,
          is_complete: true,
        },
      }),
    })

    render(<MetricsCards filters={DEFAULT_FILTERS} timezone="UTC" />)

    expect(await screen.findAllByText('No usage in this period')).toHaveLength(4)
  })

  it('surfaces an error instead of a blank card', async () => {
    globalThis.fetch = vi.fn(
      async () =>
        new Response(JSON.stringify({ detail: 'database unavailable', error: 'DatabaseError' }), {
          status: 503,
        }),
    ) as unknown as typeof fetch

    render(<MetricsCards filters={DEFAULT_FILTERS} timezone="UTC" />)

    expect(await screen.findAllByText('database unavailable')).toHaveLength(4)
  })
})

describe('ModelBreakdownTable', () => {
  const filters: DashboardFilters = DEFAULT_FILTERS

  it('lists each model with its provider and totals', async () => {
    mockFetch({ '/api/usage/models': makeModels() })

    render(<ModelBreakdownTable filters={filters} timezone="UTC" />)

    expect(await screen.findByText('sonnet')).toBeInTheDocument()
    expect(screen.getByText('free-model')).toBeInTheDocument()
    expect(screen.getByText('openrouter')).toBeInTheDocument()
    expect(screen.getByText('opencode')).toBeInTheDocument()
  })

  it('keeps the same model name from two providers on separate rows', async () => {
    mockFetch({
      '/api/usage/models': makeModels({
        models: [
          { platform: 'opencode', provider_id: 'alpha', model_id: 'sonnet', request_count: 1, totals: { input_tokens: 10, output_tokens: 1, total_tokens: 11, consumption_tokens: 11 }, unknown_total_events: 0 },
          { platform: 'opencode', provider_id: 'beta', model_id: 'sonnet', request_count: 2, totals: { input_tokens: 20, output_tokens: 2, total_tokens: 22, consumption_tokens: 22 }, unknown_total_events: 0 },
        ],
      }),
    })

    render(<ModelBreakdownTable filters={filters} timezone="UTC" />)

    expect(await screen.findAllByText('sonnet')).toHaveLength(2)
    expect(screen.getByText('alpha')).toBeInTheDocument()
    expect(screen.getByText('beta')).toBeInTheDocument()
  })

  it('keeps the same model name on two platforms on separate rows', async () => {
    mockFetch({
      '/api/usage/models': makeModels({
        models: [
          { platform: 'opencode', provider_id: 'shared', model_id: 'sonnet', request_count: 1, totals: { input_tokens: 10, output_tokens: 1, total_tokens: 11, consumption_tokens: 11 }, unknown_total_events: 0 },
          { platform: 'cline', provider_id: 'shared', model_id: 'sonnet', request_count: 2, totals: { input_tokens: 20, output_tokens: 2, total_tokens: 22, consumption_tokens: 22 }, unknown_total_events: 0 },
        ],
      }),
    })

    render(<ModelBreakdownTable filters={filters} timezone="UTC" />)

    // Same provider, same model, two assistants: both rows must survive, and the
    // platform is the only thing telling them apart.
    expect(await screen.findAllByText('sonnet')).toHaveLength(2)
    expect(screen.getByText('OpenCode')).toBeInTheDocument()
    expect(screen.getByText('Cline')).toBeInTheDocument()
  })

  it('notes records that reported no total', async () => {
    mockFetch({
      '/api/usage/models': makeModels({
        models: [
          { platform: 'opencode', provider_id: 'opencode', model_id: 'partial', request_count: 2, totals: { input_tokens: 0, output_tokens: 0, total_tokens: 0, consumption_tokens: 0 }, unknown_total_events: 2 },
        ],
      }),
    })

    render(<ModelBreakdownTable filters={filters} timezone="UTC" />)

    expect(await screen.findByText('2 records reported no total')).toBeInTheDocument()
  })

  it('shows an empty state when no model matches the filters', async () => {
    mockFetch({ '/api/usage/models': makeModels({ models: [] }) })

    render(<ModelBreakdownTable filters={filters} timezone="UTC" />)

    expect(await screen.findByText('No models match the current filters.')).toBeInTheDocument()
  })

  it('offers a retry when the request fails', async () => {
    globalThis.fetch = vi.fn(async () => new Response('{}', { status: 502 })) as unknown as typeof fetch

    render(<ModelBreakdownTable filters={filters} timezone="UTC" />)

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})

describe('TrackingStatusPanel', () => {
  it('reports detection, last sync, and imported count', async () => {
    mockFetch({ '/api/collector/status': makeCollectorStatus() })

    render(<TrackingStatusPanel />)

    expect(await screen.findByText('Detected')).toBeInTheDocument()
    expect(screen.getByText('1,990 events')).toBeInTheDocument()
    expect(screen.getByText('Tracking active')).toBeInTheDocument()
  })

  it('treats an absent OpenCode as a state rather than an error', async () => {
    mockFetch({
      '/api/collector/status': makeCollectorStatus({
        available: false,
        status: 'never_scanned',
        stored_events: 0,
        detail: 'no OpenCode database file at the resolved path',
      }),
    })

    render(<TrackingStatusPanel />)

    expect(await screen.findByText('Not found')).toBeInTheDocument()
    expect(screen.getByText('Not detected')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('reports detection per platform without naming the wrong one', async () => {
    mockFetch({
      '/api/collector/status': {
        collectors: [
          { platform: 'opencode', available: true, status: 'idle', source_path: '/a', storage_format: 'sqlite', detail: '', checkpoint: null, last_scan_at: '2026-10-11T11:49:09Z', stored_events: 2540 },
          { platform: 'cline', available: true, status: 'idle', source_path: '/b', storage_format: 'json+sqlite-index', detail: '', checkpoint: null, last_scan_at: '2026-10-11T11:49:10Z', stored_events: 2142 },
        ],
        generated_at: '2026-10-11T12:00:00Z',
      },
    })

    render(<TrackingStatusPanel />)

    expect(await screen.findByText('OpenCode')).toBeInTheDocument()
    expect(screen.getByText('Cline')).toBeInTheDocument()
    // Each row is labelled by what it detects, not by a hard-coded assistant name.
    expect(screen.getAllByText('Detection')).toHaveLength(2)
    expect(screen.getAllByText('Detected')).toHaveLength(2)
  })

  it('warns when the last scan failed but usage is intact', async () => {
    mockFetch({ '/api/collector/status': makeCollectorStatus({ status: 'error' }) })

    render(<TrackingStatusPanel />)

    expect(await screen.findByText('Sync failed')).toBeInTheDocument()
    expect(screen.getByText(/Stored usage is unaffected/)).toBeInTheDocument()
  })

  it('reports a completed rescan', async () => {
    const user = userEvent.setup()
    const stub = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/api/collector/rescan') && init?.method === 'POST') {
        return new Response(
          JSON.stringify([
            {
              platform: 'opencode',
              mode: 'historical',
              succeeded: true,
              scanned: 1990,
              inserted: 3,
              updated: 1987,
              stored: 1990,
              skipped_in_flight: 1,
              checkpoint: '1791719340504',
              duration_seconds: 1.04,
              started_at: '2026-10-11T12:00:00Z',
              finished_at: '2026-10-11T12:00:01Z',
              error_message: '',
            },
          ]),
          { status: 200 },
        )
      }
      return new Response(JSON.stringify(makeCollectorStatus()), { status: 200 })
    })
    globalThis.fetch = stub as unknown as typeof fetch

    render(<TrackingStatusPanel />)
    await user.click(await screen.findByRole('button', { name: 'Rescan now' }))

    expect(await screen.findByText('Rescan complete — 3 new records stored.')).toBeInTheDocument()
  })

  it('reports a failed rescan without hiding it', async () => {
    const user = userEvent.setup()
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith('/api/collector/rescan') && init?.method === 'POST') {
        return new Response(
          JSON.stringify([
            {
              platform: 'opencode',
              mode: 'historical',
              succeeded: false,
              scanned: 0,
              inserted: 0,
              updated: 0,
              stored: 0,
              skipped_in_flight: 0,
              checkpoint: null,
              duration_seconds: 0.2,
              started_at: '2026-10-11T12:00:00Z',
              finished_at: '2026-10-11T12:00:00Z',
              error_message: 'source is locked',
            },
          ]),
          { status: 200 },
        )
      }
      return new Response(JSON.stringify(makeCollectorStatus()), { status: 200 })
    }) as unknown as typeof fetch

    render(<TrackingStatusPanel />)
    await user.click(await screen.findByRole('button', { name: 'Rescan now' }))

    expect(await screen.findByText(/source is locked/)).toBeInTheDocument()
  })
})

describe('FilterBar', () => {
  it('offers the ranges the backend supports', async () => {
    mockFetch({ '/api/usage/models': makeModels() })

    render(<FilterBar filters={DEFAULT_FILTERS} onChange={() => {}} timezone="UTC" />)

    const select = await screen.findByLabelText('Date range')
    const values = [...select.querySelectorAll('option')].map((option) => option.value)

    expect(values).toContain('today')
    expect(values).toContain('all_time')
    expect(values).toContain('custom')
  })

  it('populates provider and model options from stored usage', async () => {
    mockFetch({ '/api/usage/models': makeModels() })

    render(<FilterBar filters={DEFAULT_FILTERS} onChange={() => {}} timezone="UTC" />)

    const provider = await screen.findByLabelText('Provider')
    expect([...provider.querySelectorAll('option')].map((o) => o.value)).toEqual([
      '',
      'opencode',
      'openrouter',
    ])

    const model = screen.getByLabelText('Model')
    expect([...model.querySelectorAll('option')].map((o) => o.value)).toEqual([
      '',
      'free-model',
      'sonnet',
    ])
  })

  it('populates platform options from stored usage', async () => {
    mockFetch({
      '/api/usage/models': makeModels({
        models: [
          { platform: 'opencode', provider_id: 'opencode', model_id: 'sonnet', request_count: 2, totals: { input_tokens: 20, output_tokens: 2, total_tokens: 22, consumption_tokens: 22 }, unknown_total_events: 0 },
          { platform: 'cline', provider_id: 'cline', model_id: 'gemini', request_count: 3, totals: { input_tokens: 30, output_tokens: 3, total_tokens: 33, consumption_tokens: 33 }, unknown_total_events: 0 },
        ],
      }),
    })

    render(<FilterBar filters={DEFAULT_FILTERS} onChange={() => {}} timezone="UTC" />)

    const platform = await screen.findByLabelText('Platform')

    // The stored ids are the values sent to the api; only the visible text is prettied.
    expect([...platform.querySelectorAll('option')].map((o) => o.value)).toEqual([
      '',
      'cline',
      'opencode',
    ])
    expect([...platform.querySelectorAll('option')].map((o) => o.textContent)).toEqual([
      'All platforms',
      'Cline',
      'OpenCode',
    ])
  })

  it('reports a chosen platform in the next filters', async () => {
    const user = userEvent.setup()
    mockFetch({ '/api/usage/models': makeModels() })
    const onChange = vi.fn()

    render(<FilterBar filters={DEFAULT_FILTERS} onChange={onChange} timezone="UTC" />)

    await user.selectOptions(await screen.findByLabelText('Platform'), 'opencode')

    expect(onChange).toHaveBeenCalledWith({ ...DEFAULT_FILTERS, platform: 'opencode' })
  })

  it('offers a new platform without a frontend change', async () => {
    // The option list is derived from stored usage, so an assistant added later
    // shows up here without editing this component.
    mockFetch({
      '/api/usage/models': makeModels({
        models: [
          { platform: 'codex', provider_id: 'openai', model_id: 'gpt', request_count: 1, totals: { input_tokens: 1, output_tokens: 1, total_tokens: 2, consumption_tokens: 2 }, unknown_total_events: 0 },
        ],
      }),
    })

    render(<FilterBar filters={DEFAULT_FILTERS} onChange={() => {}} timezone="UTC" />)

    const platform = await screen.findByLabelText('Platform')

    // An unrecognised id falls back to itself rather than rendering blank.
    expect([...platform.querySelectorAll('option')].map((o) => o.value)).toContain('codex')
    expect(screen.getByRole('option', { name: 'codex' })).toBeInTheDocument()
  })

  it('reveals date inputs only for a custom range', async () => {
    mockFetch({ '/api/usage/models': makeModels() })

    const { rerender } = render(
      <FilterBar filters={DEFAULT_FILTERS} onChange={() => {}} timezone="UTC" />,
    )
    expect(screen.queryByLabelText('From')).not.toBeInTheDocument()

    rerender(
      <FilterBar
        filters={{ ...DEFAULT_FILTERS, range: 'custom' }}
        onChange={() => {}}
        timezone="UTC"
      />,
    )
    expect(screen.getByLabelText('From')).toBeInTheDocument()
    expect(screen.getByLabelText('To')).toBeInTheDocument()
  })

  it('reports a range change to its owner', async () => {
    const user = userEvent.setup()
    const changes: DashboardFilters[] = []
    mockFetch({ '/api/usage/models': makeModels() })

    render(
      <FilterBar
        filters={DEFAULT_FILTERS}
        onChange={(next) => changes.push(next)}
        timezone="UTC"
      />,
    )

    await user.selectOptions(await screen.findByLabelText('Date range'), 'current_month')

    expect(changes).toHaveLength(1)
    expect(changes[0]?.range).toBe('current_month')
  })

  it('keeps filters usable when the option list fails to load', async () => {
    globalThis.fetch = vi.fn(async () => new Response('{}', { status: 500 })) as unknown as typeof fetch

    render(<FilterBar filters={DEFAULT_FILTERS} onChange={() => {}} timezone="UTC" />)

    const provider = await screen.findByLabelText('Provider')
    expect([...provider.querySelectorAll('option')]).toHaveLength(1)
  })
})
