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

/** A value of a datetime-local input (browser time) as UTC ISO, or undefined when empty or invalid. */
export function localToIso(value: string | undefined): string | undefined {
  if (!value) return undefined
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString()
}

export interface ChartSpan {
  range: TimeRange
  interval: TimeseriesInterval
  label: string
  description: string
}

const MAX_CHART_MS = 366 * 24 * 60 * 60 * 1000 // the longest range GET /dashboard/timeseries accepts

/** The range and bucket size of a chart for optional from/to values. Without "from" it shows the last 24 hours. */
export function chartSpan(start: string | undefined, end: string | undefined, now: Date = new Date()): ChartSpan {
  const until = end ? new Date(end) : now
  const since = start
    ? new Date(Math.max(new Date(start).getTime(), until.getTime() - MAX_CHART_MS))
    : new Date(until.getTime() - 24 * 60 * 60 * 1000)
  const hours = (until.getTime() - since.getTime()) / 3_600_000
  const [interval, label]: [TimeseriesInterval, string] =
    hours <= 2 ? ['1m', 'minute'] : hours <= 12 ? ['15m', '15 min'] : hours <= 72 ? ['1h', 'hour'] : ['1d', 'day']
  return {
    range: { start_time: since.toISOString(), end_time: until.toISOString() },
    interval,
    label,
    description: start || end ? 'selected range' : 'last 24 hours',
  }
}

/** API time range ending now, as UTC ISO strings (the API requires a timezone). */
export function rangeToTimes(id: RangeId, now: Date = new Date()): TimeRange {
  const { seconds } = getRange(id)
  return {
    start_time: new Date(now.getTime() - seconds * 1000).toISOString(),
    end_time: now.toISOString(),
  }
}
