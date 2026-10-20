import { api } from './client'

export const SEVERITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const
export type Severity = (typeof SEVERITIES)[number]

// Mirrors DetectionResponse in services/api/app/features/detections/list_detections/response.py
export interface Detection {
  detection_id: string
  created_at: string
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

/** Latest detections, newest first. Filters and paging come with the history endpoint (API gap G5). */
export function getLatestDetections(limit = 50): Promise<Detection[]> {
  return api<Detection[]>('/detections', { query: { limit } })
}
