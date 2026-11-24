import { api } from './client'
import type { Severity } from './detections'

export interface TimeRange {
  start_time: string
  end_time: string
}

export interface DashboardSummary {
  flow_count: number
  detection_count: number
  alert_count: number
}

export function getSummary(range: TimeRange): Promise<DashboardSummary> {
  return api<DashboardSummary>('/dashboard/summary', { query: { ...range } })
}

export type TimeseriesInterval = '10s' | '30s' | '1m' | '5m' | '15m' | '1h' | '1d'

export interface TimeseriesPoint {
  timestamp: string
  flows_count: number
  detections_count: number
  detections_by_severity: Record<Severity, number>
}

export interface Timeseries {
  interval: TimeseriesInterval
  data: TimeseriesPoint[]
}

export function getTimeseries(range: TimeRange, interval: TimeseriesInterval): Promise<Timeseries> {
  return api<Timeseries>('/dashboard/timeseries', { query: { ...range, interval } })
}
