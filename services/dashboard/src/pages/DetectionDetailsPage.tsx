import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { getDetection } from '../api/detections'
import { DetectionEvidence } from '../components/DetectionEvidence'
import { Loading } from '../components/QueryStatus'
import { SeverityBadge } from '../components/SeverityBadge'
import { describeError } from '../lib/errors'
import { formatType } from '../lib/format'
import { usePageTitle } from '../lib/usePageTitle'

export function DetectionDetailsPage() {
  const { id = '' } = useParams()
  const detection = useQuery({ queryKey: ['detection', id], queryFn: () => getDetection(id) })
  usePageTitle('Detection details')

  if (detection.isError) {
    const notFound =
      detection.error instanceof ApiError && (detection.error.status === 404 || detection.error.status === 422)
    return (
      <section className="card">
        <p className="error" role="alert">
          {notFound ? 'Detection not found.' : `Could not load the detection. ${describeError(detection.error)}`}
        </p>
        <Link to="/history">Back to history</Link>
      </section>
    )
  }
  if (!detection.data) return <Loading what="the detection" />

  const d = detection.data
  return (
    <>
      <p className="small">
        <Link to="/history">History</Link> <span className="muted">/ {d.detection_id}</span>
      </p>
      <div className="page-head">
        <div className="alert-title">
          <SeverityBadge severity={d.severity} />
          <h1>
            {formatType(d.type)}
            {d.src_ip ? ` from ${d.src_ip}` : ''}
          </h1>
        </div>
      </div>
      <DetectionEvidence detection={d} />
    </>
  )
}
