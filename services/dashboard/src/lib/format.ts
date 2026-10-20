const numberFormat = new Intl.NumberFormat('en-US')

export function formatNumber(n: number): string {
  return numberFormat.format(n)
}

export function formatTime(iso: string | number): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// Detection types from detection.v1.json plus the six classes of Vision v1.1.
const TYPE_LABELS: Record<string, string> = {
  port_scan: 'Port Scan',
  dos: 'DoS/DDoS-like Traffic',
  brute_force: 'Brute Force',
  abnormal_traffic: 'Abnormal Traffic',
  abnormal_pattern: 'Abnormal Traffic',
  suspicious_pattern: 'Suspicious Connection Pattern',
  unknown: 'Unknown Anomaly',
}

export function formatType(type: string): string {
  return TYPE_LABELS[type] ?? type.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export function formatConfidence(c: number | null): string {
  return c === null ? '-' : c.toFixed(2)
}
