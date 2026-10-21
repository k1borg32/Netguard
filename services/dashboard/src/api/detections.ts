import { api } from './client'

export const SEVERITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const
export type Severity = (typeof SEVERITIES)[number]

// Mirrors DetectionResponse in services/api/app/features/detections/list_detections/response.py
export interface Detection {
  detection_id: string
  created_at: string
  first_ingested_at: string | null
  last_ingested_at: string | null
  type: string
  method: string
  severity: Severity
  confidence: number | null
  src_ip: string | null
  dst_ip: string | null
  window_size_s: number | null
  features: Record<string, unknown> | null
  explanation: string | null
}

export interface ListDetectionsResponse {
  items: Detection[]
  total: number
  page: number
  page_size: number
}

/** Latest detections, newest first, from the first page. */
export async function getLatestDetections(limit = 50): Promise<Detection[]> {
  const response = await api<ListDetectionsResponse>('/detections', { query: { page: 1, page_size: limit } })
  return response.items
}
