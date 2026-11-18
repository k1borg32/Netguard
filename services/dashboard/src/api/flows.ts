import { api } from './client'

// Mirrors FlowResponse in services/api/app/features/flows/common/response.py.
// Leaves out `label`: that is ground truth for the quality metrics and is not shown to the operator.
export interface Flow {
  flow_id: string
  ts_start: string
  trace_id: string | null
  ingested_at: string | null
  duration_ms: number | null
  src_ip: string | null
  dst_ip: string | null
  src_port: number | null
  dst_port: number | null
  protocol: string | null
  packets: number | null
  bytes: number | null
  tcp_flags: string | null
  source: string | null
}

export interface FlowPage {
  items: Flow[]
  total: number
  page: number
  page_size: number
}

export interface FlowFilters {
  start_time?: string
  end_time?: string
  src_ip?: string
  dst_ip?: string
  src_port?: string
  dst_port?: string
  protocol?: string
  page?: number
  page_size?: number
}

export function getFlows(filters: FlowFilters): Promise<FlowPage> {
  return api<FlowPage>('/flows', { query: { ...filters } })
}

export function getFlow(id: string, tsStart: string): Promise<Flow> {
  return api<Flow>(`/flows/${encodeURIComponent(id)}`, { query: { tsStart } })
}
