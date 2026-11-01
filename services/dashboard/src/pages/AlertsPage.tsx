import { keepPreviousData, useQuery } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { getAlerts, type AlertFilters, type AlertListItem } from '../api/alerts'
import { ApiError } from '../api/client'
import { SEVERITIES } from '../api/detections'
import { AcknowledgeButton } from '../components/AcknowledgeButton'
import { AlertStatusBadge } from '../components/AlertStatusBadge'
import { SeverityBadge } from '../components/SeverityBadge'
import { DETECTION_TYPES, formatConfidence, formatDateTime, formatNumber, formatType } from '../lib/format'
import { RANGES, rangeToTimes, type RangeId } from '../lib/timeRange'

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
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page')) || 1)

  /** Every filter change goes back to page 1; filters live in the URL, so a view can be reloaded and shared. */
  function setFilter(name: string, value: string) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.delete('page')
      if (value) next.set(name, value)
      else next.delete(name)
      return next
    })
  }

  function setPage(value: number) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.set('page', String(value))
      return next
    })
  }

  const range = params.get('range') as RangeId | null
  const filters: AlertFilters = {
    status: params.get('status') ?? undefined,
    severity: params.get('severity') ?? undefined,
    detection_type: params.get('type') ?? undefined,
    src_ip: params.get('src') ?? undefined,
    dst_ip: params.get('dst') ?? undefined,
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

  function onTextFilter(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
  }

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

      <form className="card filters" onSubmit={onTextFilter} aria-label="Alert filters">
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
        <label>
          Source IP
          {/* Applied on Enter or when leaving the field, not on every key, so half an address is never sent. */}
          <input
            key={`src-${filters.src_ip ?? ''}`}
            defaultValue={filters.src_ip ?? ''}
            placeholder="e.g. 10.0.0.5"
            onBlur={(e) => setFilter('src', e.target.value.trim())}
            onKeyDown={(e) => e.key === 'Enter' && setFilter('src', e.currentTarget.value.trim())}
          />
        </label>
        <label>
          Destination IP
          <input
            key={`dst-${filters.dst_ip ?? ''}`}
            defaultValue={filters.dst_ip ?? ''}
            onBlur={(e) => setFilter('dst', e.target.value.trim())}
            onKeyDown={(e) => e.key === 'Enter' && setFilter('dst', e.currentTarget.value.trim())}
          />
        </label>
        <button type="button" className="btn" onClick={() => setParams(new URLSearchParams())}>
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
          <div className="pager">
            <span className="muted small">
              {formatNumber(data.total)} alerts · page {data.page} of {Math.max(1, data.total_pages)}
            </span>
            <span className="pager-buttons">
              <button type="button" className="btn btn-small" disabled={!data.has_previous} onClick={() => setPage(page - 1)}>
                Previous
              </button>
              <button type="button" className="btn btn-small" disabled={!data.has_next} onClick={() => setPage(page + 1)}>
                Next
              </button>
            </span>
          </div>
        </section>
      )}
    </>
  )
}
