import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Detection } from '../api/detections'
import { OverviewPage } from './OverviewPage'

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

const requests: string[] = []

function renderOverview(detections: Partial<Detection>[], flowCount = 182430) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      requests.push(url)
      if (url.startsWith('/api/v1/dashboard/summary')) {
        return json({ flow_count: flowCount, detection_count: 37, alert_count: 9 })
      }
      if (url.startsWith('/api/v1/dashboard/timeseries')) {
        return json({ start_time: 'a', end_time: 'b', interval: '30s', data: [] })
      }
      if (url.startsWith('/api/v1/alerts')) {
        return json({ items: [], total: 4, page: 1, page_size: 1, total_pages: 4, has_next: true, has_previous: false })
      }
      if (url.startsWith('/api/v1/detections')) {
        return json({ items: detections, total: detections.length, page: 1, page_size: 500 })
      }
      throw new Error(`unexpected request ${url}`)
    }),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <OverviewPage />
    </QueryClientProvider>,
  )
}

const base: Detection = {
  detection_id: '7c1e9a42-0000-0000-0000-00000000d03f',
  created_at: new Date().toISOString(),
  first_ingested_at: null,
  last_ingested_at: null,
  type: 'port_scan',
  method: 'rule',
  severity: 'HIGH',
  confidence: 0.94,
  src_ip: '10.66.6.6',
  dst_ip: '10.1.0.1',
  window_size_s: 10,
  features: { unique_dst_ports: 212 },
  explanation: '10.66.6.6 contacted 212 distinct destination ports in 10s (threshold 3).',
}

describe('OverviewPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    requests.length = 0
  })

  it('shows the summary counts and the latest detections', async () => {
    renderOverview([base])

    expect(await screen.findByText('182,430')).toBeInTheDocument()
    expect(screen.getByText('37')).toBeInTheDocument()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('Port Scan')).toBeInTheDocument()
    expect(within(table).getByText('HIGH')).toBeInTheDocument()
    expect(within(table).getByText('10.66.6.6')).toBeInTheDocument()
  })

  it('shows HTML from a detection as text, never as markup (SEC-08)', async () => {
    const payload = '<img src=x onerror="alert(1)">'
    const { container } = renderOverview([{ ...base, type: payload, src_ip: payload }])

    // type and source in the table, type in the breakdown
    expect(await screen.findAllByText(payload)).toHaveLength(3)
    expect(container.querySelector('img')).toBeNull()
  })

  it('counts open alerts and asks for the traffic series of the selected range', async () => {
    renderOverview([base])

    expect(await screen.findByText('4')).toBeInTheDocument()
    expect(requests.some((u) => u.includes('/alerts?status=NEW&page_size=1'))).toBe(true)
    const series = requests.find((u) => u.includes('/dashboard/timeseries')) ?? ''
    expect(series).toContain('start_time=')
    expect(series).toContain('end_time=')
    expect(series).toContain('interval=30s')
  })

  it('lists every detection class with its count', async () => {
    renderOverview([base, { ...base, detection_id: 'second' }])

    await waitFor(() => {
      const name = screen.getAllByText('Port Scan').find((e) => e.classList.contains('type-name'))
      expect(name?.closest('li')).toHaveTextContent('2')
    })
    expect(screen.getByText('Unknown Anomaly').closest('li')).toHaveTextContent('0')
  })

  it('explains why imported files with old timestamps show no flows', async () => {
    renderOverview([base], 0)
    expect(await screen.findByText(/No flows in this range/)).toBeInTheDocument()
  })

  it('tells the user how to get data when there are no detections', async () => {
    renderOverview([])
    expect(await screen.findByText(/No detections yet/)).toBeInTheDocument()
  })
})
