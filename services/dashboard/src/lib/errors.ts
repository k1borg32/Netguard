import { ApiError } from '../api/client'

/** One sentence that tells the user what went wrong, instead of "Failed to fetch" or a bare status code. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429)
      return 'Too many requests: the API is limiting this dashboard, it tries again in a few seconds.'
    if (error.status === 403) return 'Your account is not allowed to do this.'
    if (error.status === 503) return 'The API is running, but its database is not reachable (503).'
    if (error.status >= 500) return `The API had an internal error (${error.status}).`
    return error.message
  }
  // fetch() rejects with a TypeError when there is no answer at all (API down, network gone).
  if (error instanceof TypeError) return "The API can't be reached. Check that the system is running."
  return error instanceof Error ? error.message : String(error)
}

/** Network errors, 5xx and 429 (rate limiting) can go away by themselves; other 4xx won't. */
export function isRetryable(error: unknown): boolean {
  if (!(error instanceof ApiError)) return true
  return error.status === 429 || error.status >= 500
}
