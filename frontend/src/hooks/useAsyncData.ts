/**
 * Loading, error, and data states for one API call.
 *
 * Each panel on the dashboard fetches independently, so they each need this rather than
 * a single app-wide flag. Treating the three states as one value means no panel can
 * accidentally render a half-finished body: there is no way to hold data and an error
 * at the same time.
 */

import { useCallback, useEffect, useState } from 'react'

import { ApiError, NetworkError } from '../api/errors'

export type AsyncState<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; error: Error }

export interface UseAsyncData<T> {
  state: AsyncState<T>
  reload: () => void
}

export function useAsyncData<T>(load: () => Promise<T>, deps: unknown[]): UseAsyncData<T> {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })

    load()
      .then((data) => {
        if (!cancelled) {
          setState({ status: 'ready', data })
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({ status: 'error', error: toError(error) })
        }
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt])

  const reload = useCallback(() => {
    setAttempt((previous) => previous + 1)
  }, [])

  return { state, reload }
}

/**
 * Describe an error the way the panel should show it.
 *
 * A network failure and a rejected request need different wording: the first means the
 * backend is not running, the second means it answered and refused.
 */
export function describeError(error: Error): { title: string; hint: string } {
  if (error instanceof NetworkError) {
    return {
      title: 'Cannot reach the Tokenly API',
      hint: 'Start the backend with `python main.py`, then retry.',
    }
  }
  if (error instanceof ApiError && error.isRetryable) {
    return {
      title: 'The Tokenly API reported a problem',
      hint: error.message,
    }
  }
  return { title: 'Something went wrong', hint: error.message }
}

function toError(error: unknown): Error {
  if (error instanceof Error) {
    return error
  }
  return new Error(String(error))
}
