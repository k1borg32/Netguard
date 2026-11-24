// The charts in words, for screen readers (the SVG itself says nothing useful to them).

import type { TimeseriesPoint } from '../api/dashboard'
import { SEVERITIES } from '../api/detections'
import { formatNumber, formatTime } from './format'

export function trafficSummary(data: TimeseriesPoint[]): string {
  if (data.length === 0) return 'No traffic in this range.'
  const total = data.reduce((sum, p) => sum + p.flows_count, 0)
  const peak = data.reduce((max, p) => (p.flows_count > max.flows_count ? p : max), data[0])
  return `${formatNumber(total)} flows in the range; the busiest interval was ${formatTime(peak.timestamp)} with ${formatNumber(peak.flows_count)} flows.`
}

export function detectionsSummary(data: TimeseriesPoint[]): string {
  const total = data.reduce((sum, p) => sum + p.detections_count, 0)
  if (total === 0) return 'No detections in this range.'
  const bySeverity = SEVERITIES.map(
    (s) => `${data.reduce((sum, p) => sum + (p.detections_by_severity[s] ?? 0), 0)} ${s}`,
  )
  return `${total} detections in the range: ${bySeverity.join(', ')}.`
}
