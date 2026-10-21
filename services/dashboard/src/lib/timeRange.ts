import type { TimeRange } from '../api/dashboard'

export const RANGES = [
  { id: '5m', label: 'Last 5 minutes', seconds: 5 * 60, bucketSeconds: 10 },
  { id: '15m', label: 'Last 15 minutes', seconds: 15 * 60, bucketSeconds: 30 },
  { id: '1h', label: 'Last hour', seconds: 60 * 60, bucketSeconds: 2 * 60 },
  { id: '24h', label: 'Last 24 hours', seconds: 24 * 60 * 60, bucketSeconds: 60 * 60 },
] as const

export type RangeId = (typeof RANGES)[number]['id']
export type RangeOption = (typeof RANGES)[number]

export function getRange(id: RangeId): RangeOption {
  return RANGES.find((r) => r.id === id) ?? RANGES[1]
}

/** API time range ending now, as UTC ISO strings (the API requires a timezone). */
export function rangeToTimes(id: RangeId, now: Date = new Date()): TimeRange {
  const { seconds } = getRange(id)
  return {
    start_time: new Date(now.getTime() - seconds * 1000).toISOString(),
    end_time: now.toISOString(),
  }
}
