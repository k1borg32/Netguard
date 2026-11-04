const numberFormat = new Intl.NumberFormat('en-US')
const compactFormat = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })

export function formatNumber(n: number): string {
  return numberFormat.format(n)
}

/** For chart axes: 1,500 stays in full, 12,000 becomes 12K. */
export function formatAxisNumber(n: number): string {
  return n < 10_000 ? numberFormat.format(n) : compactFormat.format(n)
}

export function formatTime(iso: string | number): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatClock(iso: string | number): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
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

// The detection classes from detection.v1.json, in the order the dashboard lists them.
export const DETECTION_TYPES: Record<string, string> = {
  port_scan: 'Port Scan',
  dos: 'DoS/DDoS-like Traffic',
  brute_force: 'Brute Force',
  abnormal_traffic: 'Abnormal Traffic',
  suspicious_pattern: 'Suspicious Connection Pattern',
  unknown: 'Unknown Anomaly',
}

export function formatType(type: string): string {
  return DETECTION_TYPES[type] ?? type.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export function formatConfidence(c: number | null): string {
  return c === null ? '-' : c.toFixed(2)
}
