import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/client'
import { Loading, LoadError } from './QueryStatus'

describe('Loading and LoadError', () => {
  it('announces loading to screen readers', () => {
    render(<Loading what="alerts" />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading alerts...')
  })

  it('reports a failed first load as an alert, in plain words', () => {
    render(<LoadError what="alerts" error={new TypeError('Failed to fetch')} />)
    expect(screen.getByRole('alert')).toHaveTextContent("Could not load alerts. The API can't be reached.")
  })

  it('keeps old data visible and says how old it is when only a refresh failed', () => {
    const updatedAt = new Date(2026, 10, 24, 15, 4, 43).getTime()
    render(<LoadError what="alerts" error={new ApiError(503, 'Database storage unavailable')} updatedAt={updatedAt} />)
    const notice = screen.getByRole('status')
    expect(notice).toHaveTextContent(/Showing alerts from .*15:04:43.*the last refresh failed/)
    expect(notice).toHaveTextContent('database is not reachable')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
