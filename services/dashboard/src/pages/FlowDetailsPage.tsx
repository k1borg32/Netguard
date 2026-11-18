import { useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router'
import { ApiError } from '../api/client'
import { getFlow } from '../api/flows'
import { endpoint, formatDateTime, formatDuration, formatNumber } from '../lib/format'

function perSecond(value: number | null, durationMs: number | null): string {
  if (value === null || !durationMs) return '-'
  return formatNumber(Math.round((value * 1000) / durationMs))
}

export function FlowDetailsPage() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  const tsStart = params.get('tsStart') ?? ''
  const flow = useQuery({ queryKey: ['flow', id, tsStart], queryFn: () => getFlow(id, tsStart) })

  if (flow.isError) {
    const notFound = flow.error instanceof ApiError && (flow.error.status === 404 || flow.error.status === 422)
    return (
      <section className="card">
        <p className="error">{notFound ? 'Flow not found.' : `Could not load the flow: ${flow.error.message}`}</p>
        <Link to="/flows">Back to flows</Link>
      </section>
    )
  }
  if (!flow.data) return <p className="muted">Loading...</p>

  const f = flow.data
  const rows: [string, string][] = [
    ['Start', formatDateTime(f.ts_start)],
    ['Duration', formatDuration(f.duration_ms)],
    ['Source', endpoint(f.src_ip, f.src_port)],
    ['Destination', endpoint(f.dst_ip, f.dst_port)],
    ['Protocol', f.protocol ?? '-'],
    ['Packets', f.packets === null ? '-' : formatNumber(f.packets)],
    ['Bytes', f.bytes === null ? '-' : formatNumber(f.bytes)],
    ['Packets / s', perSecond(f.packets, f.duration_ms)],
    ['Bytes / s', perSecond(f.bytes, f.duration_ms)],
    ['TCP flags', f.tcp_flags ?? '-'],
    ['Input', f.source ?? '-'],
    ['Ingested at', f.ingested_at ? formatDateTime(f.ingested_at) : '-'],
    ['Flow ID', f.flow_id],
    ['Trace ID', f.trace_id ?? '-'],
  ]

  return (
    <>
      <p className="small">
        <Link to="/flows">Flows</Link> <span className="muted">/ {f.flow_id}</span>
      </p>
      <div className="page-head">
        <h1>
          {endpoint(f.src_ip, f.src_port)} to {endpoint(f.dst_ip, f.dst_port)}
        </h1>
      </div>
      <section className="card">
        <dl className="kv">
          {rows.map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>
    </>
  )
}
