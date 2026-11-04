import type { TimeRange, TimeseriesInterval } from '../api/dashboard'

interface Range {
  id: string
  label: string
  seconds: number
  /** Bucket size of the charts: about 30-60 bars per range, 24 for the longer ones. */
  interval: TimeseriesInterval
  intervalLabel: string
  /** The bars are shorter than a minute, so the time axis needs seconds. */
  showSeconds: boolean
}

export const RANGES = [
  { id: '5m', label: 'Last 5 minutes', seconds: 5 * 60, interval: '10s', intervalLabel: '10 s', showSeconds: true },
  { id: '15m', label: 'Last 15 minutes', seconds: 15 * 60, interval: '30s', intervalLabel: '30 s', showSeconds: true },
  { id: '1h', label: 'Last hour', seconds: 60 * 60, interval: '1m', intervalLabel: 'minute', showSeconds: false },
  { id: '6h', label: 'Last 6 hours', seconds: 6 * 60 * 60, interval: '15m', intervalLabel: '15 min', showSeconds: false },
  { id: '24h', label: 'Last 24 hours', seconds: 24 * 60 * 60, interval: '1h', intervalLabel: 'hour', showSeconds: false },
] as const satisfies readonly Range[]

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
