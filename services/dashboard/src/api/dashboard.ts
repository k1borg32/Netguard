import { api } from './client'

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
