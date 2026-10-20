import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, clearTokens, getRefreshToken, onSessionExpired, setTokens, toQueryString } from './client'

function json(status: number, body: unknown): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const pair = (n: number) => ({ access_token: `access-${n}`, refresh_token: `refresh-${n}`, token_type: 'bearer' })

function authHeader(call: unknown[]): string | undefined {
  const init = call[1] as RequestInit
  return (init.headers as Record<string, string>).Authorization
}

describe('api client', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    clearTokens()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    onSessionExpired(() => {})
  })

  it('sends the access token and the query string', async () => {
    setTokens(pair(1))
    fetchMock.mockResolvedValueOnce(json(200, { ok: true }))

    await api('/dashboard/summary', { query: { start_time: 'a', end_time: 'b', empty: '' } })

    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/dashboard/summary?start_time=a&end_time=b')
    expect(authHeader(fetchMock.mock.calls[0])).toBe('Bearer access-1')
  })

  it('refreshes once on 401 and repeats the request with the new token', async () => {
    setTokens(pair(1))
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: 'Authentication failed' }))
      .mockResolvedValueOnce(json(200, pair(2)))
      .mockResolvedValueOnce(json(200, { flow_count: 1 }))

    const result = await api<{ flow_count: number }>('/dashboard/summary')

    expect(result.flow_count).toBe(1)
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/auth/refresh')
    expect(authHeader(fetchMock.mock.calls[1])).toBe('Bearer refresh-1')
    expect(authHeader(fetchMock.mock.calls[2])).toBe('Bearer access-2')
    expect(getRefreshToken()).toBe('refresh-2')
  })

  it('shares one refresh call between parallel requests', async () => {
    setTokens(pair(1))
    fetchMock.mockImplementation(async (url: string, init: RequestInit) => {
      const auth = (init.headers as Record<string, string>).Authorization
      if (url === '/api/v1/auth/refresh') return json(200, pair(2))
      return auth === 'Bearer access-2' ? json(200, { ok: true }) : json(401, { detail: 'expired' })
    })

    await Promise.all([api('/alerts'), api('/detections'), api('/auth/me')])

    const refreshCalls = fetchMock.mock.calls.filter((c) => c[0] === '/api/v1/auth/refresh')
    expect(refreshCalls).toHaveLength(1)
  })

  it('ends the session when the refresh token is rejected', async () => {
    setTokens(pair(1))
    const expired = vi.fn()
    onSessionExpired(expired)
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: 'Authentication failed' }))
      .mockResolvedValueOnce(json(401, { detail: 'Authentication failed' }))

    await expect(api('/alerts')).rejects.toMatchObject({ status: 401 })
    expect(expired).toHaveBeenCalledOnce()
    expect(getRefreshToken()).toBeNull()
  })

  it('does not refresh for login (auth: false) and returns the API detail', async () => {
    fetchMock.mockResolvedValueOnce(json(401, { detail: 'Authentication failed' }))

    const err = await api('/auth/login', { method: 'POST', body: {}, auth: false }).catch((e: unknown) => e)

    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).message).toBe('Authentication failed')
    expect(fetchMock).toHaveBeenCalledOnce()
  })
})

describe('toQueryString', () => {
  it('skips empty values and encodes the rest', () => {
    expect(toQueryString({ a: undefined, b: null, c: '', d: 0, e: '2026-01-01T00:00:00+01:00' })).toBe(
      '?d=0&e=2026-01-01T00%3A00%3A00%2B01%3A00',
    )
    expect(toQueryString({})).toBe('')
  })
})
