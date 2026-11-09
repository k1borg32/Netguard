import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DetectionDetailsPage } from './DetectionDetailsPage'
import { FlowDetailsPage } from './FlowDetailsPage'
import { FlowsPage } from './FlowsPage'
import { HistoryPage } from './HistoryPage'

const DETECTION_ID = '93710f47-d789-54f6-9688-e439027c238d'
const FLOW_ID = 'a8106b12-718d-437d-9a7a-71205075097f'
const TS = '2026-11-01T21:26:21Z'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const detection = {
  detection_id: DETECTION_ID,
  created_at: '2026-11-01T21:26:24Z',
  first_ingested_at: '2026-11-01T21:26:20Z',
  last_ingested_at: '2026-11-01T21:26:23Z',
  type: 'brute_force',
  method: 'rule',
  severity: 'LOW',
  confidence: 0.61,
  src_ip: '10.40.0.1',
  dst_ip: '10.1.0.4',
  src_port: null,
  dst_port: null,
  protocol: null,
  window_size_s: 60,
  window_start: '2026-11-01T21:26:00Z',
  window_end: '2026-11-01T21:27:00Z',
  explanation: '10.40.0.1 made 52 connection attempts',
  features: { attempts: 52 },
  trace_ids: ['trace-1'],
}

const flow = {
  flow_id: FLOW_ID,
  ts_start: TS,
  trace_id: 'trace-1',
  ingested_at: '2026-11-01T21:26:22Z',
  duration_ms: 500,
  src_ip: '10.40.0.1',
  dst_ip: '10.1.0.4',
  src_port: 30001,
  dst_port: 22,
  protocol: 'TCP',
  packets: 10,
  bytes: 3000,
  tcp_flags: 'S',
  source: 'flowfile',
  label: 'ground-truth-secret',
}

interface Stub {
  detections?: unknown[]
  flows?: unknown[]
  total?: number
  status?: number
}

function stubApi({ detections = [detection], flows = [flow], total, status = 200 }: Stub = {}) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      calls.push(url)
      if (status !== 200) return json({ detail: [] }, status)
      if (url.startsWith('/api/v1/dashboard/timeseries')) return json({ interval: '1h', data: [] })
      if (url.includes('/flows') && url.includes('/detections/')) {
        return json({ items: [flow], total: 1, page: 1, page_size: 50 })
      }
      if (url.startsWith(`/api/v1/detections/${DETECTION_ID}`)) return json(detection)
      if (url.startsWith('/api/v1/detections')) {
        return json({ items: detections, total: total ?? detections.length, page: 1, page_size: 20 })
      }
      if (url.startsWith(`/api/v1/flows/${FLOW_ID}`)) return json(flow)
      if (url.startsWith('/api/v1/flows')) {
        return json({ items: flows, total: total ?? flows.length, page: 1, page_size: 50 })
      }
      throw new Error(`unexpected request ${url}`)
    }),
  )
  return calls
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/history/:id" element={<DetectionDetailsPage />} />
          <Route path="/flows" element={<FlowsPage />} />
          <Route path="/flows/:id" element={<FlowDetailsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('HistoryPage (F13, UC-04)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists detections, also the LOW ones that raise no alert', async () => {
    stubApi()
    renderAt('/history')

    const row = (await screen.findByRole('link', { name: 'Brute Force' })).closest('tr') as HTMLElement
    expect(within(row).getByText('LOW')).toBeInTheDocument()
    expect(within(row).getByText('rule')).toBeInTheDocument()
    expect(within(row).getByText('10.40.0.1')).toBeInTheDocument()
  })

  it('sends time, type, severity, method and source filters from the URL', async () => {
    const calls = stubApi()
    renderAt('/history?from=2026-11-01T10:00&to=2026-11-02T10:00&severity=HIGH&type=dos&method=rule&src=10.0.0.5&page=2')

    await screen.findByRole('link', { name: 'Brute Force' })
    const request = calls.find((c) => c.startsWith('/api/v1/detections')) ?? ''
    expect(request).toContain('start_time=')
    expect(request).toContain('end_time=')
    expect(request).toContain('severity=HIGH')
    expect(request).toContain('detection_type=dos')
    expect(request).toContain('method=rule')
    expect(request).toContain('src_ip=10.0.0.5')
    expect(request).toContain('page=2')
    expect(screen.getByLabelText('Type')).toHaveValue('dos')
  })

  it('goes back to page 1 when a filter changes', async () => {
    const calls = stubApi()
    renderAt('/history?page=3')

    await screen.findByRole('link', { name: 'Brute Force' })
    await userEvent.selectOptions(screen.getByLabelText('Severity'), 'CRITICAL')

    await waitFor(() => {
      const last = calls.filter((c) => c.includes('severity=CRITICAL')).at(-1)
      expect(last).toContain('page=1')
    })
  })

  it('moves between pages', async () => {
    const calls = stubApi({ total: 45 })
    renderAt('/history')

    await screen.findByText(/page 1 of 3/)
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(calls.some((c) => c.startsWith('/api/v1/detections') && c.includes('page=2'))).toBe(true))
  })

  it('asks the chart for the last 24 hours in hourly buckets by default', async () => {
    const calls = stubApi()
    renderAt('/history')

    await screen.findByRole('link', { name: 'Brute Force' })
    const chart = calls.find((c) => c.includes('/dashboard/timeseries')) ?? ''
    expect(chart).toContain('interval=1h')
    expect(screen.getByRole('heading', { name: /per hour, last 24 hours/ })).toBeInTheDocument()
  })

  it('reloads only with the Refresh button, it does not poll', async () => {
    const calls = stubApi()
    renderAt('/history')

    await screen.findByRole('link', { name: 'Brute Force' })
    const before = calls.filter((c) => c.startsWith('/api/v1/detections')).length
    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(calls.filter((c) => c.startsWith('/api/v1/detections')).length).toBe(before + 1))
  })

  it('explains an empty result and an invalid filter', async () => {
    stubApi({ detections: [] })
    const { unmount } = renderAt('/history')
    expect(await screen.findByText(/No detections match/)).toBeInTheDocument()
    unmount()

    stubApi({ status: 422 })
    renderAt('/history?src=nope')
    expect(await screen.findByText(/Check the filters/)).toBeInTheDocument()
  })

  it('shows HTML from a detection as text, never as markup (SEC-08)', async () => {
    const payload = '<img src=x onerror="alert(1)">'
    stubApi({ detections: [{ ...detection, type: payload, src_ip: payload }] })
    const { container } = renderAt('/history')

    expect(await screen.findAllByText(payload)).toHaveLength(2)
    expect(container.querySelector('img')).toBeNull()
  })
})

describe('DetectionDetailsPage (UC-03)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the evidence of a detection that has no alert', async () => {
    stubApi()
    renderAt(`/history/${DETECTION_ID}`)

    expect(await screen.findByRole('heading', { name: 'Brute Force from 10.40.0.1' })).toBeInTheDocument()
    expect(screen.getByText(/made 52 connection attempts/)).toBeInTheDocument()
    expect(screen.getByText('attempts')).toBeInTheDocument()
    expect(await screen.findByText('10.40.0.1:30001')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).toBeNull()
  })

  it('says so when the detection does not exist', async () => {
    stubApi({ status: 404 })
    renderAt(`/history/${DETECTION_ID}`)
    expect(await screen.findByText('Detection not found.')).toBeInTheDocument()
  })
})

describe('FlowsPage (UC-08)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists flows and never shows the ground-truth label', async () => {
    stubApi()
    renderAt('/flows')

    const row = (await screen.findByText('10.40.0.1:30001')).closest('tr') as HTMLElement
    expect(within(row).getByText('10.1.0.4:22')).toBeInTheDocument()
    expect(within(row).getByText('TCP')).toBeInTheDocument()
    expect(within(row).getByText('3,000')).toBeInTheDocument()
    expect(within(row).getByText('flowfile')).toBeInTheDocument()
    expect(screen.queryByText('ground-truth-secret')).toBeNull()
  })

  it('sends IP, port and protocol filters', async () => {
    const calls = stubApi()
    renderAt('/flows?src=10.40.0.1&dst=10.1.0.4&sport=30001&dport=22&protocol=TCP')

    await screen.findByText('10.40.0.1:30001')
    expect(calls[0]).toContain('src_ip=10.40.0.1')
    expect(calls[0]).toContain('dst_ip=10.1.0.4')
    expect(calls[0]).toContain('src_port=30001')
    expect(calls[0]).toContain('dst_port=22')
    expect(calls[0]).toContain('protocol=TCP')
  })

  it('links each flow to its details with the start time the API needs', async () => {
    stubApi()
    renderAt('/flows')

    await screen.findByText('10.40.0.1:30001')
    const link = screen.getByRole('link', { name: /2026|11/ })
    expect(link).toHaveAttribute('href', `/flows/${FLOW_ID}?tsStart=${encodeURIComponent(TS)}`)
  })

  it('explains an invalid port', async () => {
    stubApi({ status: 422 })
    renderAt('/flows?dport=99999')
    expect(await screen.findByText(/Check the filters/)).toBeInTheDocument()
  })
})

describe('FlowDetailsPage (UC-08)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows all fields with packets and bytes per second, but not the label', async () => {
    const calls = stubApi()
    renderAt(`/flows/${FLOW_ID}?tsStart=${encodeURIComponent(TS)}`)

    expect(await screen.findByRole('heading', { name: '10.40.0.1:30001 to 10.1.0.4:22' })).toBeInTheDocument()
    expect(calls[0]).toContain(`tsStart=${encodeURIComponent(TS)}`)
    expect(screen.getByText('Packets / s').closest('div')).toHaveTextContent('20')
    expect(screen.getByText('Bytes / s').closest('div')).toHaveTextContent('6,000')
    expect(screen.getByText('trace-1')).toBeInTheDocument()
    expect(screen.queryByText('ground-truth-secret')).toBeNull()
  })

  it('says so when the flow does not exist', async () => {
    stubApi({ status: 404 })
    renderAt(`/flows/${FLOW_ID}?tsStart=${encodeURIComponent(TS)}`)
    expect(await screen.findByText('Flow not found.')).toBeInTheDocument()
  })
})
