import { describe, expect, it } from 'vitest'
import { rangeToTimes } from './timeRange'

describe('rangeToTimes', () => {
  it('returns a UTC range ending now, which the summary endpoint accepts', () => {
    const now = new Date('2026-10-20T12:15:00Z')
    expect(rangeToTimes('15m', now)).toEqual({
      start_time: '2026-10-20T12:00:00.000Z',
      end_time: '2026-10-20T12:15:00.000Z',
    })
    expect(rangeToTimes('24h', now).start_time).toBe('2026-10-19T12:15:00.000Z')
  })
})
