/**
 * Fixtures shaped exactly like the backend's responses.
 *
 * Building these by hand rather than mocking loosely keeps the tests honest: if the API
 * changes a field name, these fixtures change with it and the tests fail loudly rather
 * than rendering `undefined`.
 */

import { vi } from 'vitest'

import type {
  CollectorStatusResponse,
  ModelBreakdownResponse,
  SummaryResponse,
  TimelineResponse,
} from '../api/types'

export function makeTotals(input: number, output: number) {
  return {
    input_tokens: input,
    output_tokens: output,
    total_tokens: input + output,
    consumption_tokens: input + output,
  }
}

export function makeSummary(overrides: Partial<SummaryResponse> = {}): SummaryResponse {
  return {
    window: {
      range: 'all_time',
      label: 'all_time',
      start: null,
      end: null,
      timezone: 'UTC',
    },
    filters: { platform: null, provider_id: null, model_id: null },
    totals: makeTotals(1000, 250),
    completeness: {
      request_count: 4,
      known_total_events: 4,
      unknown_total_events: 0,
      is_complete: true,
    },
    generated_at: '2026-10-11T12:00:00Z',
    ...overrides,
  }
}

export function makeModels(overrides: Partial<ModelBreakdownResponse> = {}): ModelBreakdownResponse {
  return {
    window: {
      range: 'all_time',
      label: 'all_time',
      start: null,
      end: null,
      timezone: 'UTC',
    },
    filters: { platform: null, provider_id: null, model_id: null },
    models: [
      {
        platform: 'opencode',
        provider_id: 'openrouter',
        model_id: 'sonnet',
        request_count: 3,
        totals: makeTotals(900, 100),
        unknown_total_events: 0,
      },
      {
        platform: 'opencode',
        provider_id: 'opencode',
        model_id: 'free-model',
        request_count: 1,
        totals: makeTotals(100, 150),
        unknown_total_events: 0,
      },
    ],
    generated_at: '2026-10-11T12:00:00Z',
    ...overrides,
  }
}

export function makeTimeline(
  buckets: { label: string; total: number; input?: number; output?: number }[],
  overrides: Partial<TimelineResponse> = {},
): TimelineResponse {
  return {
    window: {
      range: 'last_7_days',
      label: 'last_7_days',
      start: '2026-10-05T00:00:00Z',
      end: '2026-10-12T00:00:00Z',
      timezone: 'UTC',
    },
    filters: { platform: null, provider_id: null, model_id: null },
    granularity: 'day',
    buckets: buckets.map((bucket) => {
      const input = bucket.input ?? Math.round(bucket.total * 0.8)
      return {
        start: `${bucket.label}T00:00:00Z`,
        label: bucket.label,
        request_count: bucket.total > 0 ? 1 : 0,
        totals: makeTotals(input, bucket.total - input),
      }
    }),
    generated_at: '2026-10-11T12:00:00Z',
    ...overrides,
  }
}

export function makeCollectorStatus(
  overrides: Partial<CollectorStatusResponse['collectors'][number]> = {},
): CollectorStatusResponse {
  return {
    collectors: [
      {
        platform: 'opencode',
        available: true,
        status: 'idle',
        source_path: '/home/user/.local/share/opencode/opencode.db',
        storage_format: 'sqlite',
        detail: '28 sessions, 1990 assistant messages',
        checkpoint: '1791719340504',
        last_scan_at: '2026-10-11T11:49:09Z',
        stored_events: 1990,
        ...overrides,
      },
    ],
    generated_at: '2026-10-11T12:00:00Z',
  }
}

/** A `fetch` stub that answers each path with the given body. */
export function stubFetch(routes: Record<string, unknown>) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString()
    const path = url.split('?')[0] ?? url
    const match = Object.keys(routes).find((route) => path.endsWith(route))

    if (!match) {
      return new Response(JSON.stringify({ detail: 'not found', error: 'NotFound' }), {
        status: 404,
      })
    }
    return new Response(JSON.stringify(routes[match]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
}
