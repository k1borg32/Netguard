import type { AlertStatus } from '../api/alerts'

export function AlertStatusBadge({ status }: { status: AlertStatus }) {
  return <span className={`status status-${status.toLowerCase()}`}>{status}</span>
}
