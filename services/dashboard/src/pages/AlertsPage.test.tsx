import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AlertDetailsPage } from './AlertDetailsPage'
import { AlertsPage } from './AlertsPage'

const ALERT_ID = '74366bed-ad2a-51fc-8413-155d4f548f5f'
const DETECTION_ID = '93710f47-d789-54f6-9688-e439027c238d'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const alert = {
  alert_id: ALERT_ID,
  detection_id: DETECTION_ID,
  status: 'NEW',
  created_at: '2026-11-01T21:26:26Z',
  acknowledged_at: null,
}

const detection = {
  detection_id: DETECTION_ID,
  created_at: '2026-11-01T21:26:24Z',
  first_ingested_at: '2026-11-01T21:26:20Z',
  type: 'port_scan',
  method: 'rule',
  severity: 'MEDIUM',
  confidence: 0.651,
  src_ip: '10.66.6.6',
  dst_ip: '10.1.0.1',
  src_port: null,
  dst_port: null,
  protocol: null,
  window_size_s: 10,
  window_start: '2026-11-01T21:26:20Z',
  window_end: '2026-11-01T21:26:30Z',
  explanation: '10.66.6.6 contacted 151 distinct destination ports',
  features: { unique_dst_ports: 151, threshold: 100 },
  trace_ids: ['trace-1'],
}

const flow = {
  flow_id: 'f1',
  ts_start: '2026-11-01T21:26:21Z',
  trace_id: 'trace-1',
  src_ip: '10.66.6.6',
  dst_ip: '10.1.0.1',
  src_port: 61980,
  dst_port: 22,
  protocol: 'TCP',
  packets: 1,
  bytes: 139,
  tcp_flags: 'S',
  label: 'ground-truth-secret',
}

function page(items: unknown[]) {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: 1, has_next: false, has_previous: false }
}

interface Api {
  items?: unknown[]
  listStatus?: number
  detailStatus?: number
}

function stubApi({ items = [{ ...alert, detection }], listStatus = 200, detailStatus = 200 }: Api = {}) {
  const state = { status: 'NEW' as string, acknowledged: false }
  const calls: { url: string; method: string }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      calls.push({ url, method })
      if (method === 'PATCH') {
        state.status = 'ACKNOWLEDGED'
        return json({ ...alert, status: state.status })
      }
      if (url.includes(`/detections/${DETECTION_ID}/flows`)) return json(page([flow]))
      if (url.includes(`/alerts/${ALERT_ID}`)) {
        if (detailStatus !== 200) return json({ detail: 'Alert not found' }, detailStatus)
        return json({ ...alert, status: state.status, detection })
      }
      if (url.startsWith('/api/v1/alerts')) {
        if (listStatus !== 200) return json({ detail: [] }, listStatus)
        return json(page(items.map((i) => ({ ...(i as object), status: state.status }))))
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
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/alerts/:id" element={<AlertDetailsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AlertsPage', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the detection fields of each alert from the list, without a request per row', async () => {
    const calls = stubApi()
    renderAt('/alerts')

    const row = (await screen.findByRole('link', { name: 'Port Scan' })).closest('tr') as HTMLElement
    expect(within(row).getByText('MEDIUM')).toBeInTheDocument()
    expect(within(row).getByText('10.66.6.6')).toBeInTheDocument()
    expect(within(row).getByText('10.1.0.1')).toBeInTheDocument()
    expect(within(row).getByText('0.65')).toBeInTheDocument()
    expect(calls.some((c) => c.url.endsWith(`/alerts/${ALERT_ID}`))).toBe(false)
  })

  it('sends the filters from the URL and from the controls, and goes back to page 1', async () => {
    const calls = stubApi()
    renderAt('/alerts?status=NEW&page=3')

    await screen.findByRole('link', { name: 'Port Scan' })
    expect(calls[0].url).toContain('status=NEW')
    expect(calls[0].url).toContain('page=3')

    await userEvent.selectOptions(screen.getByLabelText('Severity'), 'HIGH')
    await waitFor(() => {
      const last = calls.filter((c) => c.url.includes('severity=HIGH')).at(-1)
      expect(last?.url).toContain('page=1')
      expect(last?.url).toContain('status=NEW')
    })
  })

  it('applies a source IP when leaving the field', async () => {
    const calls = stubApi()
    renderAt('/alerts')

    await userEvent.type(await screen.findByLabelText('Source IP'), '10.0.0.5')
    expect(calls.some((c) => c.url.includes('src_ip='))).toBe(false)
    await userEvent.tab()
    await waitFor(() => expect(calls.some((c) => c.url.includes('src_ip=10.0.0.5'))).toBe(true))
  })

  it('acknowledges an alert and updates the row', async () => {
    const calls = stubApi()
    renderAt('/alerts')

    await userEvent.click(await screen.findByRole('button', { name: 'Acknowledge' }))

    expect(calls.some((c) => c.method === 'PATCH' && c.url.endsWith(`/alerts/${ALERT_ID}/acknowledge`))).toBe(true)
    const row = (await screen.findByRole('link', { name: 'Port Scan' })).closest('tr') as HTMLElement
    expect(await within(row).findByText('ACKNOWLEDGED')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).toBeNull()
  })

  it('explains an empty list and an invalid filter', async () => {
    stubApi({ items: [] })
    const { unmount } = renderAt('/alerts')
    expect(await screen.findByText(/No alerts match these filters/)).toBeInTheDocument()
    unmount()

    stubApi({ listStatus: 422 })
    renderAt('/alerts?src=nope')
    expect(await screen.findByText(/IP address is not valid/)).toBeInTheDocument()
  })
})

describe('AlertDetailsPage', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the evidence: explanation, feature values and contributing flows (F09, F15)', async () => {
    stubApi()
    renderAt(`/alerts/${ALERT_ID}`)

    expect(await screen.findByRole('heading', { name: 'Port Scan from 10.66.6.6' })).toBeInTheDocument()
    expect(screen.getByText(/contacted 151 distinct destination ports/)).toBeInTheDocument()
    expect(screen.getByText('unique_dst_ports')).toBeInTheDocument()
    expect(screen.getByText('151')).toBeInTheDocument()
    expect(await screen.findByText('10.66.6.6:61980')).toBeInTheDocument()
    expect(screen.getByText('trace-1')).toBeInTheDocument()
  })

  it('never shows the ground-truth label of a flow', async () => {
    stubApi()
    renderAt(`/alerts/${ALERT_ID}`)

    await screen.findByText('10.66.6.6:61980')
    expect(screen.queryByText('ground-truth-secret')).toBeNull()
  })

  it('shows HTML from a detection as text, never as markup (SEC-08)', async () => {
    const payload = '<img src=x onerror="alert(1)">'
    stubApi()
    const original = vi.mocked(fetch).getMockImplementation()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.endsWith(`/alerts/${ALERT_ID}`)) {
          return json({ ...alert, detection: { ...detection, explanation: payload, features: { evil: payload } } })
        }
        return (original as NonNullable<typeof original>)(url, init)
      }),
    )
    const { container } = renderAt(`/alerts/${ALERT_ID}`)

    expect(await screen.findAllByText(payload)).toHaveLength(2)
    expect(container.querySelector('img')).toBeNull()
  })

  it('acknowledges from the details page', async () => {
    stubApi()
    renderAt(`/alerts/${ALERT_ID}`)

    await userEvent.click(await screen.findByRole('button', { name: 'Acknowledge' }))
    expect(await screen.findByText('ACKNOWLEDGED')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).toBeNull()
  })

  it('says so when the alert does not exist', async () => {
    stubApi({ detailStatus: 404 })
    renderAt(`/alerts/${ALERT_ID}`)
    expect(await screen.findByText('Alert not found.')).toBeInTheDocument()
  })
})
