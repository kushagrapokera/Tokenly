import { describe, expect, it } from 'vitest'

import { buildQuery } from './client'
import { ApiError, NetworkError, toApiError } from './errors'

describe('buildQuery', () => {
  it('encodes supplied values', () => {
    expect(buildQuery({ range: 'today', timezone: 'UTC' })).toBe('range=today&timezone=UTC')
  })

  it('omits empty values so backend defaults still apply', () => {
    expect(buildQuery({ range: 'today', model_id: null, provider_id: undefined, platform: '' })).toBe(
      'range=today',
    )
  })

  it('returns an empty string when nothing is set', () => {
    expect(buildQuery({ range: null })).toBe('')
  })

  it('encodes values needing escapes', () => {
    expect(buildQuery({ provider_id: 'a b&c' })).toBe('provider_id=a+b%26c')
  })
})

describe('toApiError', () => {
  it('reads the backend error shape', async () => {
    const response = new Response(
      JSON.stringify({ detail: 'unknown timezone', error: 'InvalidTimezoneError' }),
      { status: 400 },
    )

    const error = await toApiError(response)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(400)
    expect(error.errorName).toBe('InvalidTimezoneError')
    expect(error.message).toBe('unknown timezone')
  })

  it('still produces an error when the body is not JSON', async () => {
    const response = new Response('<html>gateway timeout</html>', { status: 504 })

    const error = await toApiError(response)

    expect(error.status).toBe(504)
    expect(error.message).toContain('504')
  })

  it('marks server errors as retryable and client errors as not', async () => {
    const serverError = await toApiError(new Response('{}', { status: 500 }))
    const clientError = await toApiError(new Response('{}', { status: 400 }))

    expect(serverError.isRetryable).toBe(true)
    expect(clientError.isRetryable).toBe(false)
  })
})

describe('NetworkError', () => {
  it('carries the reason the API could not be reached', () => {
    const error = new NetworkError('backend is not running')

    expect(error).toBeInstanceOf(Error)
    expect(error.message).toBe('backend is not running')
  })
})
