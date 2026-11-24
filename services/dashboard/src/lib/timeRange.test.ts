import { describe, expect, it } from 'vitest'
import { chartSpan, localToIso, rangeToTimes } from './timeRange'

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

describe('chartSpan', () => {
  const now = new Date('2026-11-09T12:00:00Z')

  it('shows the last 24 hours in hourly buckets without a time filter', () => {
    const span = chartSpan(undefined, undefined, now)
    expect(span.range.start_time).toBe('2026-11-08T12:00:00.000Z')
    expect(span.interval).toBe('1h')
    expect(span.description).toBe('last 24 hours')
  })

  it('picks finer buckets for short ranges and daily ones for long ranges', () => {
    expect(chartSpan('2026-11-09T11:00:00Z', '2026-11-09T12:00:00Z', now).interval).toBe('1m')
    expect(chartSpan('2026-11-09T04:00:00Z', '2026-11-09T12:00:00Z', now).interval).toBe('15m')
    expect(chartSpan('2026-10-01T00:00:00Z', '2026-11-09T12:00:00Z', now).interval).toBe('1d')
  })

  it('never asks for more than the 366 days the API accepts', () => {
    const span = chartSpan('2020-01-01T00:00:00Z', undefined, now)
    const days = (Date.parse(span.range.end_time) - Date.parse(span.range.start_time)) / 86_400_000
    expect(days).toBe(366)
  })
})

describe('localToIso', () => {
  it('returns undefined for an empty or impossible value', () => {
    expect(localToIso(undefined)).toBeUndefined()
    expect(localToIso('')).toBeUndefined()
    expect(localToIso('not a date')).toBeUndefined()
  })

  it('converts a datetime-local value to UTC', () => {
    expect(localToIso('2026-11-09T12:00')).toBe(new Date(2026, 10, 9, 12, 0).toISOString())
  })
})
