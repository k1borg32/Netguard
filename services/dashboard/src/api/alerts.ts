import { api } from './client'
import type { Severity } from './detections'

export type AlertStatus = 'NEW' | 'ACKNOWLEDGED'

// Mirrors AlertResponse and ListAlertsResponse in services/api/app/features/alerts
export interface Alert {
  alert_id: string
  detection_id: string
  status: AlertStatus
  created_at: string
  acknowledged_at: string | null
}

export interface AlertPage {
  items: AlertListItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

// Mirrors AlertDetectionResponse in services/api/app/features/alerts/get_alert/response.py
export interface AlertDetection {
  detection_id: string
  created_at: string
  first_ingested_at: string | null
  type: string
  method: string
  severity: Severity
  confidence: number | null
  src_ip: string | null
  dst_ip: string | null
  src_port: number | null
  dst_port: number | null
  protocol: string | null
  window_size_s: number | null
  window_start: string | null
  window_end: string | null
  explanation: string | null
  features: Record<string, unknown> | null
  trace_ids: string[]
}

export interface AlertDetails extends Alert {
  detection: AlertDetection
}

/** The short form of the detection that each list item carries. */
export type AlertListItem = Alert & {
  detection: Pick<AlertDetection, 'type' | 'severity' | 'confidence' | 'src_ip' | 'dst_ip' | 'protocol'>
}

export interface AlertFilters {
  start_time?: string
  end_time?: string
  status?: string
  severity?: string
  detection_type?: string
  src_ip?: string
  dst_ip?: string
  page?: number
  page_size?: number
}

export function getAlerts(filters: AlertFilters): Promise<AlertPage> {
  return api<AlertPage>('/alerts', { query: { ...filters } })
}

/** Number of alerts nobody has acknowledged yet, whatever their age. */
export async function getOpenAlertCount(): Promise<number> {
  const page = await getAlerts({ status: 'NEW', page_size: 1 })
  return page.total
}

export function getAlert(id: string): Promise<AlertDetails> {
  return api<AlertDetails>(`/alerts/${encodeURIComponent(id)}`)
}

export function acknowledgeAlert(id: string): Promise<Alert> {
  return api<Alert>(`/alerts/${encodeURIComponent(id)}/acknowledge`, { method: 'PATCH' })
}
