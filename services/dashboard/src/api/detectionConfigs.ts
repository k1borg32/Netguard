import { api } from './client'

export const METHODS = ['rule', 'statistical'] as const

export type ParameterValue = string | number | boolean | null | ParameterValue[] | { [key: string]: ParameterValue }
export type Parameters = Record<string, ParameterValue>

// Mirrors DetectionConfigurationResponse in services/api/app/features/detection_configurations/common/response.py
export interface DetectionConfig {
  configuration_id: string
  detection_type: string
  method: string
  parameters: Parameters
  active: boolean
}

export interface DetectionConfigPage {
  items: DetectionConfig[]
  total: number
  page: number
  page_size: number
}

export interface NewDetectionConfig {
  detection_type: string
  method: string
  parameters: Parameters
}

export function getDetectionConfigs(page = 1, pageSize = 100): Promise<DetectionConfigPage> {
  return api<DetectionConfigPage>('/detection-configurations', { query: { page, page_size: pageSize } })
}

export function getDetectionConfig(id: string): Promise<DetectionConfig> {
  return api<DetectionConfig>(`/detection-configurations/${encodeURIComponent(id)}`)
}

/** Admin only. New configurations are stored inactive. */
export function createDetectionConfig(config: NewDetectionConfig): Promise<DetectionConfig> {
  return api<DetectionConfig>('/detection-configurations', { method: 'POST', body: config })
}

/** Admin only. The parameters object replaces the stored one as a whole, so send every key. */
export function updateDetectionConfig(id: string, parameters: Parameters): Promise<DetectionConfig> {
  return api<DetectionConfig>(`/detection-configurations/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: { parameters },
  })
}

/** Admin only. Other configurations stay as they are; the API has no way to deactivate one. */
export function activateDetectionConfig(id: string): Promise<DetectionConfig> {
  return api<DetectionConfig>(`/detection-configurations/${encodeURIComponent(id)}/activate`, { method: 'PUT' })
}
