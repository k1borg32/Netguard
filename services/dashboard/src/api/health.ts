export interface Health {
  status: 'ok' | 'degraded'
  db: 'ok' | 'unavailable'
}

/** GET /health of the API, proxied by nginx as /api/health. No token needed. */
export async function getHealth(): Promise<Health> {
  const res = await fetch('/api/health', { headers: { Accept: 'application/json' } })
  if (!res.ok) throw new Error(`API health returned ${res.status}`)
  return (await res.json()) as Health
}
