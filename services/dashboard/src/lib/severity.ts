import type { Severity } from '../api/detections'

// One hue, light to dark, because severity has an order. Same values as the badges in index.css.
export const SEVERITY_COLORS: Record<Severity, string> = {
  LOW: '#ec9f5e',
  MEDIUM: '#d96f25',
  HIGH: '#b0420f',
  CRITICAL: '#6f1a12',
}
