import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/client'
import { describeError, isRetryable } from './errors'

describe('describeError', () => {
  it('explains the errors a user can run into in plain words', () => {
    expect(describeError(new TypeError('Failed to fetch'))).toMatch(/can't be reached/)
    expect(describeError(new ApiError(429, 'Too Many Requests'))).toMatch(/Too many requests/)
    expect(describeError(new ApiError(503, 'Database storage unavailable'))).toMatch(/database is not reachable/)
    expect(describeError(new ApiError(500, 'boom'))).toBe('The API had an internal error (500).')
    expect(describeError(new ApiError(403, 'Forbidden'))).toMatch(/not allowed/)
  })

  it('keeps the API message for other client errors', () => {
    expect(describeError(new ApiError(404, 'Alert not found'))).toBe('Alert not found')
  })
})

describe('isRetryable', () => {
  it('retries what can go away by itself, and nothing else', () => {
    expect(isRetryable(new TypeError('Failed to fetch'))).toBe(true)
    expect(isRetryable(new ApiError(429, 'slow down'))).toBe(true)
    expect(isRetryable(new ApiError(503, 'db'))).toBe(true)
    expect(isRetryable(new ApiError(404, 'gone'))).toBe(false)
    expect(isRetryable(new ApiError(422, []))).toBe(false)
  })
})
