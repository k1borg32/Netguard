import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getOpenAlertCount } from '../api/alerts'
import { getSummary, getTimeseries } from '../api/dashboard'
import { getLatestDetections } from '../api/detections'
import { DetectionsChart } from '../components/DetectionsChart'
import { SeverityBadge } from '../components/SeverityBadge'
import { StatCard } from '../components/StatCard'
import { TrafficChart } from '../components/TrafficChart'
import { TypeBreakdown } from '../components/TypeBreakdown'
import { formatConfidence, formatNumber, formatTime, formatType } from '../lib/format'
import { getRange, RANGES, rangeToTimes, type RangeId } from '../lib/timeRange'

const REFRESH_MS = 5_000

export function OverviewPage() {
  const [rangeId, setRangeId] = useState<RangeId>('15m')
  const range = getRange(rangeId)

  // Times are computed inside queryFn, so every refetch moves the window to "now".
  const summary = useQuery({
    queryKey: ['dashboard-summary', rangeId],
    queryFn: () => getSummary(rangeToTimes(rangeId)),
    refetchInterval: REFRESH_MS,
    placeholderData: keepPreviousData,
  })
  const timeseries = useQuery({
    queryKey: ['dashboard-timeseries', rangeId],
    queryFn: () => getTimeseries(rangeToTimes(rangeId), range.interval),
    refetchInterval: REFRESH_MS,
    placeholderData: keepPreviousData,
  })
  const openAlerts = useQuery({
    queryKey: ['alerts', 'open-count'],
    queryFn: getOpenAlertCount,
    refetchInterval: REFRESH_MS,
  })
  const detections = useQuery({
    queryKey: ['detections', 'latest'],
    queryFn: () => getLatestDetections(500),
    refetchInterval: REFRESH_MS,
  })

  // The breakdown by type ends at the time of the last fetch, so it moves with every refresh.
  const start = detections.dataUpdatedAt - range.seconds * 1000
  const inRange = (detections.data ?? []).filter((d) => Date.parse(d.created_at) >= start)
  const s = summary.data

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Overview</h1>
          <p className="muted small">Live view - refreshes every 5 s</p>
        </div>
        <div className="page-actions">
          {summary.dataUpdatedAt > 0 && (
            <span className="muted small">Updated {formatTime(summary.dataUpdatedAt)}</span>
          )}
          <select aria-label="Time range" value={rangeId} onChange={(e) => setRangeId(e.target.value as RangeId)}>
            {RANGES.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {summary.isError && <p className="error">Could not load statistics: {summary.error.message}</p>}
      <div className="cards">
        <StatCard label="Flows" value={s ? formatNumber(s.flow_count) : '-'} hint={range.label} />
        <StatCard
          label="Flows / s (average)"
          value={s ? formatNumber(Math.round(s.flow_count / range.seconds)) : '-'}
          hint={range.label}
        />
        <StatCard label="Detections" value={s ? formatNumber(s.detection_count) : '-'} hint={range.label} />
        <StatCard
          label="Open alerts"
          value={openAlerts.data === undefined ? '-' : formatNumber(openAlerts.data)}
          hint={s ? `Not acknowledged · ${formatNumber(s.alert_count)} raised in range` : 'Not acknowledged'}
        />
      </div>

      <div className="grid-2">
        <section className="card">
          <h2>Traffic - flows per {range.intervalLabel}</h2>
          {timeseries.isError && <p className="error">Could not load traffic: {timeseries.error.message}</p>}
          {timeseries.data && <TrafficChart data={timeseries.data.data} showSeconds={range.showSeconds} />}
          {s?.flow_count === 0 && (
            <p className="muted small">
              No flows in this range. Flows count by their own start time, so a file with older timestamps only shows
              up here when it is imported with REPLAY_SPEED. Its detections show up either way.
            </p>
          )}
        </section>

        <section className="card">
          <h2>Detections by type</h2>
          <TypeBreakdown types={inRange.map((d) => d.type)} />
          <p className="muted small">From the latest 500 detections, {range.label.toLowerCase()}.</p>
        </section>

        <section className="card">
          <h2>Detections over time, by severity</h2>
          {timeseries.data && <DetectionsChart data={timeseries.data.data} showSeconds={range.showSeconds} />}
        </section>

        <section className="card">
          <h2>Latest detections</h2>
          {detections.isError && <p className="error">Could not load detections: {detections.error.message}</p>}
          {detections.data?.length === 0 && <p className="muted">No detections yet. Import a capture: make import FILE=data/pcap/sample.pcap</p>}
          {!!detections.data?.length && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Severity</th>
                    <th>Type</th>
                    <th>Source</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {detections.data.slice(0, 8).map((d) => (
                    <tr key={d.detection_id} title={d.explanation ?? undefined}>
                      <td>{formatTime(d.created_at)}</td>
                      <td>
                        <SeverityBadge severity={d.severity} />
                      </td>
                      <td>{formatType(d.type)}</td>
                      <td>{d.src_ip ?? '-'}</td>
                      <td>{formatConfidence(d.confidence)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  )
}
