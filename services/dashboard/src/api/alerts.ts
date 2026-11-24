import { api } from './client'
import type { DetectionDetails } from './detections'

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

// AlertDetectionResponse in services/api/app/features/alerts/get_alert/response.py has no last_ingested_at.
export type AlertDetection = Omit<DetectionDetails, 'last_ingested_at'>

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
