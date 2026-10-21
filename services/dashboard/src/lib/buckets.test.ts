import { describe, expect, it } from 'vitest'
import type { Detection, Severity } from '../api/detections'
import { bucketBySeverity } from './buckets'

function detection(createdAt: string, severity: Severity): Detection {
  return {
    detection_id: createdAt + severity,
    created_at: createdAt,
    type: 'port_scan',
    method: 'rule',
    severity,
    confidence: 0.9,
    src_ip: '10.66.6.6',
    dst_ip: '10.1.0.1',
    window_size_s: 10,
    features: null,
    explanation: null,
  }
}

describe('bucketBySeverity', () => {
  const start = new Date('2026-10-20T12:00:00Z')
  const end = new Date('2026-10-20T12:01:00Z')

  it('keeps empty buckets as zeros', () => {
    const buckets = bucketBySeverity([], start, end, 10)
    expect(buckets).toHaveLength(6)
    expect(buckets[0]).toEqual({ ts: start.getTime(), LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 })
  })

  it('counts each detection in its bucket and severity, ignoring ones outside the range', () => {
    const buckets = bucketBySeverity(
      [
        detection('2026-10-20T12:00:01Z', 'HIGH'),
        detection('2026-10-20T12:00:09.999Z', 'HIGH'),
        detection('2026-10-20T12:00:10Z', 'LOW'),
        detection('2026-10-20T12:00:59Z', 'CRITICAL'),
        detection('2026-10-20T11:59:59Z', 'HIGH'),
        detection('2026-10-20T12:01:00Z', 'HIGH'),
      ],
      start,
      end,
      10,
    )
    expect(buckets[0].HIGH).toBe(2)
    expect(buckets[1].LOW).toBe(1)
    expect(buckets[5].CRITICAL).toBe(1)
    const total = buckets.reduce((n, b) => n + b.LOW + b.MEDIUM + b.HIGH + b.CRITICAL, 0)
    expect(total).toBe(4)
  })
})
