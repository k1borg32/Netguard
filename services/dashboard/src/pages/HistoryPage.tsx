import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { ApiError } from '../api/client'
import { getTimeseries } from '../api/dashboard'
import { getDetections, SEVERITIES, type DetectionFilters } from '../api/detections'
import { DetectionsChart } from '../components/DetectionsChart'
import { Pager } from '../components/Pager'
import { SeverityBadge } from '../components/SeverityBadge'
import { TextFilter } from '../components/TextFilter'
import { DETECTION_TYPES, formatConfidence, formatDateTime, formatType } from '../lib/format'
import { chartSpan, localToIso } from '../lib/timeRange'
import { useUrlFilters } from '../lib/useUrlFilters'

const PAGE_SIZE = 20

export function HistoryPage() {
  const { get, page, setFilter, setPage, reset } = useUrlFilters()
  const from = get('from')
  const to = get('to')
  const filters: DetectionFilters = {
    start_time: localToIso(from),
    end_time: localToIso(to),
    severity: get('severity'),
    detection_type: get('type'),
    method: get('method'),
    src_ip: get('src'),
    dst_ip: get('dst'),
    page,
    page_size: PAGE_SIZE,
  }

  // History is looked at, not watched: it loads when the filters change, and with the Refresh button.
  const detections = useQuery({
    queryKey: ['detections', 'history', filters],
    queryFn: () => getDetections(filters),
    placeholderData: keepPreviousData,
  })
  const span = chartSpan(filters.start_time, filters.end_time)
  const chart = useQuery({
    queryKey: ['dashboard-timeseries', 'history', filters.start_time, filters.end_time],
    queryFn: () => getTimeseries(span.range, span.interval),
    placeholderData: keepPreviousData,
  })

  const data = detections.data
  const invalidFilter = detections.error instanceof ApiError && detections.error.status === 422
  // An impossible time range is already explained once, by the message above the table.
  const chartFailed = chart.isError && !(chart.error instanceof ApiError && chart.error.status === 422)

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Detection history</h1>
          <p className="muted small">All stored detections, also the ones that did not raise an alert.</p>
        </div>
        <button
          type="button"
          className="btn"
          onClick={() => {
            void detections.refetch()
            void chart.refetch()
          }}
        >
          Refresh
        </button>
      </div>

      <form className="card filters" onSubmit={(e) => e.preventDefault()} aria-label="History filters">
        <TextFilter label="From" type="datetime-local" value={from} onApply={(v) => setFilter('from', v)} />
        <TextFilter label="To" type="datetime-local" value={to} onApply={(v) => setFilter('to', v)} />
        <label>
          Type
          <select value={filters.detection_type ?? ''} onChange={(e) => setFilter('type', e.target.value)}>
            <option value="">Any</option>
            {Object.entries(DETECTION_TYPES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Severity
          <select value={filters.severity ?? ''} onChange={(e) => setFilter('severity', e.target.value)}>
            <option value="">Any</option>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Method
          <select value={filters.method ?? ''} onChange={(e) => setFilter('method', e.target.value)}>
            <option value="">Any</option>
            <option value="rule">rule</option>
            <option value="statistical">statistical</option>
          </select>
        </label>
        <TextFilter label="Source IP" value={filters.src_ip} placeholder="e.g. 10.0.0.5" onApply={(v) => setFilter('src', v)} />
        <TextFilter label="Destination IP" value={filters.dst_ip} onApply={(v) => setFilter('dst', v)} />
        <button type="button" className="btn" onClick={reset}>
          Reset
        </button>
      </form>

      <section className="card chart-gap">
        <h2>
          Detections per {span.label}, {span.description}
        </h2>
        {chartFailed && <p className="error">Could not load the chart: {chart.error?.message}</p>}
        {chart.data && <DetectionsChart data={chart.data.data} showSeconds={false} />}
        <p className="muted small">Uses the time filters only; type, severity, method and IP filter the table below.</p>
      </section>

      {invalidFilter && <p className="error">Check the filters: an IP address or the time range is not valid.</p>}
      {detections.isError && !invalidFilter && (
        <p className="error">Could not load detections: {detections.error.message}</p>
      )}
      {data?.items.length === 0 && (
        <section className="card">
          <p className="muted">No detections match these filters.</p>
        </section>
      )}
      {!!data?.items.length && (
        <section className="card">
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Severity</th>
                  <th>Type</th>
                  <th>Method</th>
                  <th>Source</th>
                  <th>Destination</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((d) => (
                  <tr key={d.detection_id}>
                    <td>{formatDateTime(d.created_at)}</td>
                    <td>
                      <SeverityBadge severity={d.severity} />
                    </td>
                    <td>
                      <Link to={`/history/${d.detection_id}`}>{formatType(d.type)}</Link>
                    </td>
                    <td>{d.method}</td>
                    <td>{d.src_ip ?? '-'}</td>
                    <td>{d.dst_ip ?? '-'}</td>
                    <td>{formatConfidence(d.confidence)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager noun="detections" total={data.total} page={data.page} pageSize={PAGE_SIZE} onPage={setPage} />
        </section>
      )}
    </>
  )
}
