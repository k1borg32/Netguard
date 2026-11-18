import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { getDetection } from '../api/detections'
import { DetectionEvidence } from '../components/DetectionEvidence'
import { SeverityBadge } from '../components/SeverityBadge'
import { formatType } from '../lib/format'

export function DetectionDetailsPage() {
  const { id = '' } = useParams()
  const detection = useQuery({ queryKey: ['detection', id], queryFn: () => getDetection(id) })

  if (detection.isError) {
    const notFound =
      detection.error instanceof ApiError && (detection.error.status === 404 || detection.error.status === 422)
    return (
      <section className="card">
        <p className="error">
          {notFound ? 'Detection not found.' : `Could not load the detection: ${detection.error.message}`}
        </p>
        <Link to="/history">Back to history</Link>
      </section>
    )
  }
  if (!detection.data) return <p className="muted">Loading...</p>

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
