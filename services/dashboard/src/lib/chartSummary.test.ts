import { describe, expect, it } from 'vitest'
import type { TimeseriesPoint } from '../api/dashboard'
import { detectionsSummary, trafficSummary } from './chartSummary'

const point = (timestamp: string, flows: number, high = 0, low = 0): TimeseriesPoint => ({
  timestamp,
  flows_count: flows,
  detections_count: high + low,
  detections_by_severity: { LOW: low, MEDIUM: 0, HIGH: high, CRITICAL: 0 },
})

describe('chart summaries for screen readers', () => {
  const data = [point('2026-11-24T14:00:00Z', 1200, 0, 3), point('2026-11-24T14:00:30Z', 4300, 2, 1)]

  it('says the total and the busiest interval of the traffic chart', () => {
    expect(trafficSummary(data)).toMatch(/^5,500 flows in the range; the busiest interval was .+ with 4,300 flows\.$/)
    expect(trafficSummary([])).toBe('No traffic in this range.')
  })

  it('says the detections per severity', () => {
    expect(detectionsSummary(data)).toBe('6 detections in the range: 4 LOW, 0 MEDIUM, 2 HIGH, 0 CRITICAL.')
    expect(detectionsSummary([point('2026-11-24T14:00:00Z', 10)])).toBe('No detections in this range.')
  })
})
