import { SEVERITIES, type Detection, type Severity } from '../api/detections'

export type SeverityBucket = { ts: number } & Record<Severity, number>

/**
 * Counts detections per time bucket and severity, for the "detections over time" chart.
 * Buckets cover [start, end) and empty buckets are kept as zeros so the chart has no gaps.
 *
 * Temporary: the chart is built from the latest detections in the browser until the API has
 * a time-series endpoint (architecture doc, API gap G1).
 */
export function bucketBySeverity(
  detections: Detection[],
  start: Date,
  end: Date,
  bucketSeconds: number,
): SeverityBucket[] {
  const step = bucketSeconds * 1000
  const first = Math.floor(start.getTime() / step) * step
  const buckets: SeverityBucket[] = []
  for (let ts = first; ts < end.getTime(); ts += step) {
    buckets.push({ ts, LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 })
  }
  for (const d of detections) {
    const t = Date.parse(d.created_at)
    if (Number.isNaN(t) || t < start.getTime() || t >= end.getTime()) continue
    const bucket = buckets[Math.floor((t - first) / step)]
    if (bucket && SEVERITIES.includes(d.severity)) bucket[d.severity] += 1
  }
  return buckets
}
