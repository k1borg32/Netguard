import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { getAlert } from '../api/alerts'
import { ApiError } from '../api/client'
import { AcknowledgeButton } from '../components/AcknowledgeButton'
import { AlertStatusBadge } from '../components/AlertStatusBadge'
import { DetectionEvidence } from '../components/DetectionEvidence'
import { SeverityBadge } from '../components/SeverityBadge'
import { formatDateTime, formatType } from '../lib/format'

const REFRESH_MS = 10_000

export function AlertDetailsPage() {
  const { id = '' } = useParams()
  const alert = useQuery({
    queryKey: ['alerts', 'detail', id],
    queryFn: () => getAlert(id),
    refetchInterval: REFRESH_MS,
  })

  if (alert.isError) {
    const notFound = alert.error instanceof ApiError && (alert.error.status === 404 || alert.error.status === 422)
    return (
      <section className="card">
        <p className="error">{notFound ? 'Alert not found.' : `Could not load the alert: ${alert.error.message}`}</p>
        <Link to="/alerts">Back to alerts</Link>
      </section>
    )
  }
  if (!alert.data) return <p className="muted">Loading...</p>

  const a = alert.data
  const d = a.detection

  return (
    <>
      <p className="small">
        <Link to="/alerts">Alerts</Link> <span className="muted">/ {a.alert_id}</span>
      </p>
      <div className="page-head">
        <div className="alert-title">
          <SeverityBadge severity={d.severity} />
          <h1>
            {formatType(d.type)}
            {d.src_ip ? ` from ${d.src_ip}` : ''}
          </h1>
          <AlertStatusBadge status={a.status} />
        </div>
        {a.status === 'NEW' && <AcknowledgeButton alertId={a.alert_id} primary />}
      </div>

      <DetectionEvidence
        detection={d}
        extraRows={[
          ['Alert raised at', formatDateTime(a.created_at)],
          ['Acknowledged at', a.acknowledged_at ? formatDateTime(a.acknowledged_at) : '-'],
        ]}
      />
    </>
  )
}
