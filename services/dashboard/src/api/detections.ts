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

export interface DetectionFilters {
  start_time?: string
  end_time?: string
  severity?: string
  detection_type?: string
  method?: string
  src_ip?: string
  dst_ip?: string
  page?: number
  page_size?: number
}

export function getDetections(filters: DetectionFilters): Promise<ListDetectionsResponse> {
  return api<ListDetectionsResponse>('/detections', { query: { ...filters } })
}

// Mirrors GetDetectionResponse in services/api/app/features/detections/get_detection/response.py
export interface DetectionDetails {
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

export function getDetection(id: string): Promise<DetectionDetails> {
  return api<DetectionDetails>(`/detections/${encodeURIComponent(id)}`)
}

/** Latest detections, newest first, from the first page. */
export async function getLatestDetections(limit = 50): Promise<Detection[]> {
  const response = await api<ListDetectionsResponse>('/detections', { query: { page: 1, page_size: limit } })
  return response.items
}

// Mirrors DetectionFlowResponse in services/api/app/features/detections/get_detection_flows/response.py.
// Leaves out `label`: that is ground truth for the quality metrics and is not shown to the operator.
export interface DetectionFlow {
  flow_id: string
  ts_start: string
  trace_id: string | null
  src_ip: string | null
  dst_ip: string | null
  src_port: number | null
  dst_port: number | null
  protocol: string | null
  packets: number | null
  bytes: number | null
  tcp_flags: string | null
}

export interface DetectionFlowPage {
  items: DetectionFlow[]
  total: number
  page: number
  page_size: number
}

export function getDetectionFlows(detectionId: string): Promise<DetectionFlowPage> {
  return api<DetectionFlowPage>(`/detections/${encodeURIComponent(detectionId)}/flows`, { query: { page_size: 50 } })
}
