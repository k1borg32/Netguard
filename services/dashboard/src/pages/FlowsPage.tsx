import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { ApiError } from '../api/client'
import { getFlows, type FlowFilters } from '../api/flows'
import { Pager } from '../components/Pager'
import { TextFilter } from '../components/TextFilter'
import { endpoint, formatDateTime, formatDuration, formatNumber } from '../lib/format'
import { localToIso } from '../lib/timeRange'
import { useUrlFilters } from '../lib/useUrlFilters'

const PAGE_SIZE = 50
const PROTOCOLS = ['TCP', 'UDP', 'ICMP', 'OTHER']

export function FlowsPage() {
  const { get, page, setFilter, setPage, reset } = useUrlFilters()
  const from = get('from')
  const to = get('to')
  const filters: FlowFilters = {
    start_time: localToIso(from),
    end_time: localToIso(to),
    src_ip: get('src'),
    dst_ip: get('dst'),
    src_port: get('sport'),
    dst_port: get('dport'),
    protocol: get('protocol'),
    page,
    page_size: PAGE_SIZE,
  }

  const flows = useQuery({
    queryKey: ['flows', filters],
    queryFn: () => getFlows(filters),
    placeholderData: keepPreviousData,
  })

  const data = flows.data
  const invalidFilter = flows.error instanceof ApiError && flows.error.status === 422

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Network flows</h1>
          <p className="muted small">Normalised flows as stored by the persister, newest first.</p>
        </div>
        <button type="button" className="btn" onClick={() => void flows.refetch()}>
          Refresh
        </button>
      </div>

      <form className="card filters" onSubmit={(e) => e.preventDefault()} aria-label="Flow filters">
        <TextFilter label="From" type="datetime-local" value={from} onApply={(v) => setFilter('from', v)} />
        <TextFilter label="To" type="datetime-local" value={to} onApply={(v) => setFilter('to', v)} />
        <TextFilter label="Source IP" value={filters.src_ip} placeholder="e.g. 10.0.0.5" onApply={(v) => setFilter('src', v)} />
        <TextFilter label="Destination IP" value={filters.dst_ip} onApply={(v) => setFilter('dst', v)} />
        <TextFilter label="Source port" value={filters.src_port} onApply={(v) => setFilter('sport', v)} />
        <TextFilter label="Destination port" value={filters.dst_port} onApply={(v) => setFilter('dport', v)} />
        <label>
          Protocol
          <select value={filters.protocol ?? ''} onChange={(e) => setFilter('protocol', e.target.value)}>
            <option value="">Any</option>
            {PROTOCOLS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn" onClick={reset}>
          Reset
        </button>
      </form>

      {invalidFilter && <p className="error">Check the filters: an IP address, a port or the time range is not valid.</p>}
      {flows.isError && !invalidFilter && <p className="error">Could not load flows: {flows.error.message}</p>}
      {data?.items.length === 0 && (
        <section className="card">
          <p className="muted">No flows match these filters. Imported files keep their original timestamps.</p>
        </section>
      )}
      {!!data?.items.length && (
        <section className="card">
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Start</th>
                  <th>Duration</th>
                  <th>Source</th>
                  <th>Destination</th>
                  <th>Protocol</th>
                  <th>Packets</th>
                  <th>Bytes</th>
                  <th>Flags</th>
                  <th>Input</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((f) => (
                  <tr key={`${f.flow_id}-${f.ts_start}`}>
                    <td>
                      <Link to={`/flows/${f.flow_id}?tsStart=${encodeURIComponent(f.ts_start)}`}>
                        {formatDateTime(f.ts_start)}
                      </Link>
                    </td>
                    <td>{formatDuration(f.duration_ms)}</td>
                    <td>{endpoint(f.src_ip, f.src_port)}</td>
                    <td>{endpoint(f.dst_ip, f.dst_port)}</td>
                    <td>{f.protocol ?? '-'}</td>
                    <td>{f.packets === null ? '-' : formatNumber(f.packets)}</td>
                    <td>{f.bytes === null ? '-' : formatNumber(f.bytes)}</td>
                    <td>{f.tcp_flags ?? '-'}</td>
                    <td>{f.source ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager noun="flows" total={data.total} page={data.page} pageSize={PAGE_SIZE} onPage={setPage} />
        </section>
      )}
    </>
  )
}
