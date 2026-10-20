// Fetch wrapper for the NetGuard API: adds the access token, refreshes it once on 401
// and turns error responses into ApiError. Components use the functions in src/api/*,
// never fetch directly.

export const API_BASE = '/api/v1'

const REFRESH_KEY = 'netguard.refresh_token'

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

// Access token only in memory; refresh token in sessionStorage so a reload keeps the
// session and closing the tab ends it (architecture doc, section 5).
let accessToken: string | null = null

export function setTokens(pair: TokenPair): void {
  accessToken = pair.access_token
  sessionStorage.setItem(REFRESH_KEY, pair.refresh_token)
}

export function clearTokens(): void {
  accessToken = null
  sessionStorage.removeItem(REFRESH_KEY)
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_KEY)
}

export function hasAccessToken(): boolean {
  return accessToken !== null
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed with status ${status}`)
    this.status = status
    this.detail = detail
  }
}

let sessionExpired: () => void = () => {}

/** Called when a request still gets 401 after a refresh attempt. */
export function onSessionExpired(handler: () => void): void {
  sessionExpired = handler
}

// One refresh at a time: refresh rotates the token, so a second parallel call with
// the old refresh token would get 401 and log the user out.
let refreshing: Promise<boolean> | null = null

export function refreshTokens(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return Promise.resolve(false)
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${refreshToken}` },
      })
      if (!res.ok) {
        clearTokens()
        return false
      }
      setTokens((await res.json()) as TokenPair)
      return true
    } catch {
      return false
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

export type QueryValue = string | number | boolean | null | undefined

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  query?: Record<string, QueryValue>
  body?: unknown
  /** false: don't send the access token and don't try to refresh (login). */
  auth?: boolean
  headers?: Record<string, string>
  signal?: AbortSignal
}

export function toQueryString(query: Record<string, QueryValue> = {}): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.append(key, String(value))
  }
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

function send(url: string, opts: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json', ...opts.headers }
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (opts.auth !== false && accessToken) headers.Authorization = `Bearer ${accessToken}`
  return fetch(url, {
    method: opts.method ?? 'GET',
    headers,
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    signal: opts.signal,
  })
}

async function readDetail(res: Response): Promise<unknown> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    return body.detail ?? body
  } catch {
    return res.statusText
  }
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const url = `${API_BASE}${path}${toQueryString(opts.query)}`
  let res = await send(url, opts)
  if (res.status === 401 && opts.auth !== false) {
    if (await refreshTokens()) res = await send(url, opts)
    if (res.status === 401) sessionExpired()
  }
  if (!res.ok) throw new ApiError(res.status, await readDetail(res))
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
