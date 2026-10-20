import type { Severity } from '../api/detections'

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={`badge badge-${severity.toLowerCase()}`}>{severity}</span>
}
