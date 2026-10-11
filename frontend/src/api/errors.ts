/**
 * The error shape the backend returns.
 *
 * The backend answers a bad request with `{"detail": ..., "error": "SomeError"}`
 * (see `errors/handlers.py`). Carrying the error name lets the UI distinguish "you
 * asked for something impossible" from "the collector broke" without parsing prose.
 */

export class ApiError extends Error {
  readonly status: number
  readonly errorName: string

  constructor(status: number, errorName: string, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.errorName = errorName
  }

  /** True when retrying might work — a collector or database problem, not a bad request. */
  get isRetryable(): boolean {
    return this.status >= 500 || this.status === 429
  }
}

export class NetworkError extends Error {
  constructor(detail: string) {
    super(detail)
    this.name = 'NetworkError'
  }
}

/**
 * Turn a non-2xx response into an `ApiError`.
 *
 * A body that does not match the expected shape is still turned into an `ApiError`
 * rather than a crash: a wrong payload is a server problem the user needs to see
 * described, not a blank screen.
 */
export async function toApiError(response: Response): Promise<ApiError> {
  const status = response.status
  let detail = `${response.statusText} (${status})`
  let errorName = 'HttpError'

  try {
    const payload: unknown = await response.json()
    if (isErrorPayload(payload)) {
      detail = payload.detail
      errorName = payload.error
    }
  } catch {
    // A non-JSON body is left described by the status line alone.
  }

  return new ApiError(status, errorName, detail)
}

function isErrorPayload(payload: unknown): payload is { detail: string; error: string } {
  if (typeof payload !== 'object' || payload === null) {
    return false
  }
  const candidate = payload as Record<string, unknown>
  return typeof candidate['detail'] === 'string' && typeof candidate['error'] === 'string'
}
