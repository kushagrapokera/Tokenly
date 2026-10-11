/**
 * Wire shapes for the Tokenly API.
 *
 * These mirror the response bodies built in `schemas/analytics.py` and
 * `schemas/collector.py`. They are hand-written rather than generated so the
 * frontend states explicitly what it expects — and a mismatch shows up as a type
 * error rather than as `undefined` in a chart.
 */

export type RangeName =
  | 'today'
  | 'yesterday'
  | 'last_7_days'
  | 'current_month'
  | 'previous_month'
  | 'current_year'
  | 'all_time'
  | 'custom'

export type Granularity = 'day' | 'month' | 'year'

/** The interval a response covers, so a chart can label itself without guessing. */
export interface WindowInfo {
  range: RangeName
  label: string
  start: string | null
  end: string | null
  timezone: string
}

/** The dimensions a response was narrowed by; null means "not filtered". */
export interface AppliedFilters {
  platform: string | null
  provider_id: string | null
  model_id: string | null
}

export interface UsageTotals {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  consumption_tokens: number
}

/**
 * How much of the picture is backed by real numbers.
 *
 * `unknown_total_events` counts records whose totals the source never reported. They
 * contribute zero to `total_tokens`, so a card showing only a total must also show
 * this — otherwise partial data reads as complete.
 */
export interface CompletenessInfo {
  request_count: number
  known_total_events: number
  unknown_total_events: number
  is_complete: boolean
}

export interface SummaryResponse {
  window: WindowInfo
  filters: AppliedFilters
  totals: UsageTotals
  completeness: CompletenessInfo
  generated_at: string
}

export interface ModelUsage {
  provider_id: string
  model_id: string
  request_count: number
  totals: UsageTotals
  unknown_total_events: number
}

export interface ModelBreakdownResponse {
  window: WindowInfo
  filters: AppliedFilters
  models: ModelUsage[]
  generated_at: string
}

export interface TimelineBucket {
  start: string
  label: string
  request_count: number
  totals: UsageTotals
}

export interface TimelineResponse {
  window: WindowInfo
  filters: AppliedFilters
  granularity: Granularity
  buckets: TimelineBucket[]
  generated_at: string
}

export type CollectorStatus = 'idle' | 'scanning' | 'error' | 'never_scanned'

export interface CollectorStatusEntry {
  platform: string
  available: boolean
  status: CollectorStatus
  source_path: string
  storage_format: string
  detail: string
  checkpoint: string | null
  last_scan_at: string | null
  stored_events: number
}

export interface CollectorStatusResponse {
  collectors: CollectorStatusEntry[]
  generated_at: string
}

export interface RescanRun {
  platform: string
  mode: string
  succeeded: boolean
  scanned: number
  inserted: number
  updated: number
  stored: number
  skipped_in_flight: number
  checkpoint: string | null
  duration_seconds: number
  started_at: string
  finished_at: string
  error_message: string
}

export interface HealthResponse {
  status: 'ok'
  app: string
  version: string
  database_connected: boolean
}

/** The query parameters every usage endpoint accepts. */
export interface UsageQuery {
  range?: RangeName
  timezone?: string
  start?: string
  end?: string
  platform?: string | null
  provider_id?: string | null
  model_id?: string | null
}
