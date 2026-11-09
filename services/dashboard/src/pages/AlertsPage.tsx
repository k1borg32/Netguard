import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getAlerts, type AlertFilters, type AlertListItem } from '../api/alerts'
import { ApiError } from '../api/client'
import { SEVERITIES } from '../api/detections'
import { AcknowledgeButton } from '../components/AcknowledgeButton'
import { AlertStatusBadge } from '../components/AlertStatusBadge'
import { Pager } from '../components/Pager'
import { SeverityBadge } from '../components/SeverityBadge'
import { TextFilter } from '../components/TextFilter'
import { DETECTION_TYPES, formatConfidence, formatDateTime, formatType } from '../lib/format'
import { RANGES, rangeToTimes, type RangeId } from '../lib/timeRange'
import { useUrlFilters } from '../lib/useUrlFilters'

const REFRESH_MS = 5_000
const PAGE_SIZE = 20

function AlertRow({ alert }: { alert: AlertListItem }) {
  const d = alert.detection
  return (
    <tr>
      <td>{formatDateTime(alert.created_at)}</td>
      <td>
        <SeverityBadge severity={d.severity} />
      </td>
      <td>
        <Link to={`/alerts/${alert.alert_id}`}>{formatType(d.type)}</Link>
      </td>
      <td>{d.src_ip ?? '-'}</td>
      <td>{d.dst_ip ?? '-'}</td>
      <td>{formatConfidence(d.confidence)}</td>
      <td>
        <AlertStatusBadge status={alert.status} />
      </td>
      <td>{alert.status === 'NEW' && <AcknowledgeButton alertId={alert.alert_id} />}</td>
    </tr>
  )
}

export function AlertsPage() {
  const { get, page, setFilter, setPage, reset } = useUrlFilters()
  const range = get('range') as RangeId | undefined
  const filters: AlertFilters = {
    status: get('status'),
    severity: get('severity'),
    detection_type: get('type'),
    src_ip: get('src'),
    dst_ip: get('dst'),
    page,
    page_size: PAGE_SIZE,
  }

  const alerts = useQuery({
    queryKey: ['alerts', 'list', range, filters],
    // Times are computed inside queryFn, so every refetch moves the window to "now".
    queryFn: () => getAlerts({ ...filters, ...(range ? rangeToTimes(range) : {}) }),
    refetchInterval: REFRESH_MS,
    placeholderData: keepPreviousData,
  })

  const data = alerts.data
  const invalidFilter = alerts.error instanceof ApiError && alerts.error.status === 422

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Alerts</h1>
          <p className="muted small">Raised from detections of MEDIUM severity and above. Refreshes every 5 s.</p>
        </div>
      </div>

      <form className="card filters" onSubmit={(e) => e.preventDefault()} aria-label="Alert filters">
        <label>
          Time
          <select value={range ?? ''} onChange={(e) => setFilter('range', e.target.value)}>
            <option value="">Any time</option>
            {RANGES.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={filters.status ?? ''} onChange={(e) => setFilter('status', e.target.value)}>
            <option value="">Any</option>
            <option value="NEW">NEW</option>
            <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
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
        <TextFilter label="Source IP" value={filters.src_ip} placeholder="e.g. 10.0.0.5" onApply={(v) => setFilter('src', v)} />
        <TextFilter label="Destination IP" value={filters.dst_ip} onApply={(v) => setFilter('dst', v)} />
        <button type="button" className="btn" onClick={reset}>
          Reset
        </button>
      </form>

      {invalidFilter && <p className="error">Check the filters: the IP address is not valid.</p>}
      {alerts.isError && !invalidFilter && <p className="error">Could not load alerts: {alerts.error.message}</p>}
      {data?.items.length === 0 && (
        <section className="card">
          <p className="muted">
            No alerts match these filters. LOW detections don&apos;t raise an alert; they are still stored as detections.
          </p>
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
                  <th>Source</th>
                  <th>Destination</th>
                  <th>Confidence</th>
                  <th>Status</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {data.items.map((alert) => (
                  <AlertRow key={alert.alert_id} alert={alert} />
                ))}
              </tbody>
            </table>
          </div>
          <Pager noun="alerts" total={data.total} page={data.page} pageSize={PAGE_SIZE} onPage={setPage} />
        </section>
      )}
    </>
  )
}
