import { api } from './client'

// Mirrors AlertResponse and ListAlertsResponse in services/api/app/features/alerts
export interface Alert {
  alert_id: string
  detection_id: string
  status: 'NEW' | 'ACKNOWLEDGED'
  created_at: string
  acknowledged_at: string | null
}

export interface AlertPage {
  items: Alert[]
  total: number
  page: number
  page_size: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

/** Number of alerts nobody has acknowledged yet, whatever their age. */
export async function getOpenAlertCount(): Promise<number> {
  const page = await api<AlertPage>('/alerts', { query: { status: 'NEW', page_size: 1 } })
  return page.total
}
