import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../api/health'

export function HealthPill() {
  const { data, isError } = useQuery({ queryKey: ['health'], queryFn: getHealth, refetchInterval: 10_000 })
  const ok = data?.status === 'ok'
  const text = isError ? 'API unreachable' : !data ? 'API ...' : ok ? 'API · DB ok' : `API ok · DB ${data.db}`
  return (
    <span className="pill" title="GET /api/health, every 10 s">
      <span className={`dot ${ok && !isError ? 'dot-ok' : data || isError ? 'dot-bad' : ''}`} aria-hidden="true" />
      {text}
    </span>
  )
}
