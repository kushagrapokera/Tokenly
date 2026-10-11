/**
 * Typed client for the Tokenly API.
 *
 * Every call goes through `request`, which owns the two things that must not vary
 * between endpoints: how query parameters are encoded, and how a non-2xx response
 * becomes an error. Endpoints below it are one line each, so adding a call site never
 * means re-deciding how errors are surfaced.
 */

import { ApiError, NetworkError, toApiError } from './errors'
import type {
  CollectorStatusResponse,
  Granularity,
  HealthResponse,
  ModelBreakdownResponse,
  RescanRun,
  SummaryResponse,
  TimelineResponse,
  UsageQuery,
} from './types'

const BASE_URL = import.meta.env['VITE_API_BASE_URL'] ?? ''

/**
 * Encode a query object into a query string, without the leading `?`.
 *
 * Empty values are omitted rather than sent blank, so an unset filter falls through to
 * the backend's own default instead of overriding it with an empty string.
 */
export function buildQuery(
  query: Record<string, string | number | null | undefined>,
): string {
  return buildParams(query)
}

function buildParams(query: Record<string, string | number | null | undefined>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === '') {
      continue
    }
    params.set(key, String(value))
  }
  return params.toString()
}

/**
 * Perform one API call and return its parsed body.
 *
 * A failure at either stage becomes an `ApiError` or `NetworkError`, so callers only
 * ever handle one error type. This function is the only place `fetch` is called.
 */
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`
  let response: Response
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...init?.headers,
      },
    })
  } catch {
    throw new NetworkError(
      `cannot reach the Tokenly API at ${BASE_URL || 'the dev server'}; is the backend running?`,
    )
  }

  if (!response.ok) {
    throw await toApiError(response)
  }
  return (await response.json()) as T
}

/**
 * Append a usage query to a path.
 *
 * `granularity` is merged into the same encoding rather than concatenated as a second
 * `?`, so any endpoint can take both without producing a malformed URL.
 */
function usagePath(path: string, query: UsageQuery, extra?: Record<string, string>): string {
  const params = buildParams({
    range: query.range,
    timezone: query.timezone,
    start: query.start,
    end: query.end,
    platform: query.platform,
    provider_id: query.provider_id,
    model_id: query.model_id,
    ...extra,
  })
  return params ? `${path}?${params}` : path
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health')
}

export function fetchSummary(query: UsageQuery): Promise<SummaryResponse> {
  return request<SummaryResponse>(usagePath('/api/usage/summary', query))
}

export function fetchModels(query: UsageQuery): Promise<ModelBreakdownResponse> {
  return request<ModelBreakdownResponse>(usagePath('/api/usage/models', query))
}

export function fetchTimeline(
  query: UsageQuery,
  granularity: Granularity,
): Promise<TimelineResponse> {
  return request<TimelineResponse>(
    usagePath('/api/usage/timeline', query, { granularity }),
  )
}

export function fetchDaily(query: UsageQuery): Promise<TimelineResponse> {
  return request<TimelineResponse>(usagePath('/api/usage/daily', query))
}

export function fetchMonthly(query: UsageQuery): Promise<TimelineResponse> {
  return request<TimelineResponse>(usagePath('/api/usage/monthly', query))
}

export function fetchYearly(query: UsageQuery): Promise<TimelineResponse> {
  return request<TimelineResponse>(usagePath('/api/usage/yearly', query))
}

export function fetchCollectorStatus(): Promise<CollectorStatusResponse> {
  return request<CollectorStatusResponse>('/api/collector/status')
}

export function triggerRescan(): Promise<RescanRun[]> {
  return request<RescanRun[]>('/api/collector/rescan', { method: 'POST' })
}

export { ApiError, NetworkError }
