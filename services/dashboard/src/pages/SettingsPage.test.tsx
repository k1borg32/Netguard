import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { UserRole } from '../api/auth'
import type { DetectionConfig, Parameters } from '../api/detectionConfigs'
import { AuthContext, type AuthState } from '../auth/context'
import { SettingsPage } from './SettingsPage'

const PORT_SCAN_ID = '10000000-0000-0000-0000-000000000001'
const DOS_ID = '10000000-0000-0000-0000-000000000002'
const NEW_ID = '10000000-0000-0000-0000-000000000003'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function configs(): DetectionConfig[] {
  return [
    {
      configuration_id: PORT_SCAN_ID,
      detection_type: 'port_scan',
      method: 'rule',
      parameters: { window_s: 10, unique_dst_ports_threshold: 100 },
      active: true,
    },
    {
      configuration_id: DOS_ID,
      detection_type: 'dos',
      method: 'rule',
      parameters: { window_s: 1, connections_to_target_threshold: 500, services: [22, 3389] },
      active: false,
    },
  ]
}

interface Call {
  method: string
  url: string
  body?: unknown
}

function stubApi({ writeStatus = 200, writeDetail }: { writeStatus?: number; writeDetail?: unknown } = {}) {
  const stored = configs()
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = init.method ?? 'GET'
      const body = init.body ? JSON.parse(String(init.body)) : undefined
      calls.push({ method, url, body })
      if (method !== 'GET' && writeStatus !== 200) return json({ detail: writeDetail ?? 'nope' }, writeStatus)

      const id = url.match(/detection-configurations\/([^/?]+)/)?.[1]
      const config = stored.find((c) => c.configuration_id === id)
      if (method === 'GET' && !id) return json({ items: stored, total: stored.length, page: 1, page_size: 100 })
      if (method === 'GET') return config ? json(config) : json({ detail: 'Detection configuration not found' }, 404)
      if (method === 'PATCH' && config) {
        // Like JSONB, the stored object does not keep the key order.
        config.parameters = Object.fromEntries(Object.entries(body.parameters as Parameters).reverse())
        return json(config)
      }
      if (method === 'PUT' && config) {
        config.active = true
        return json(config)
      }
      if (method === 'POST') {
        const created = { configuration_id: NEW_ID, ...body, active: false }
        stored.push(created)
        return json(created, 201)
      }
      throw new Error(`unexpected ${method} ${url}`)
    }),
  )
  return calls
}

function Search() {
  return <output data-testid="search">{useLocation().search}</output>
}

function renderAt(path: string, role: UserRole = 'admin') {
  const auth: AuthState = {
    status: 'authenticated',
    user: { user_id: 'u1', username: role, role },
    expired: false,
    login: async () => {},
    logout: async () => {},
  }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={auth}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route
              path="/settings"
              element={
                <>
                  <SettingsPage />
                  <Search />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
}

describe('SettingsPage (F16, UC-07)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists the stored configurations with their status and says the engine still reads the YAML file', async () => {
    stubApi()
    renderAt('/settings')

    const row = (await screen.findByRole('link', { name: 'Edit Port Scan' })).closest('tr') as HTMLElement
    expect(within(row).getByText('Active')).toBeInTheDocument()
    expect(within(row).getByText(/unique_dst_ports_threshold 100/)).toBeInTheDocument()
    const dos = screen.getByRole('link', { name: /Edit DoS/ }).closest('tr') as HTMLElement
    expect(within(dos).getByText('Inactive')).toBeInTheDocument()
    expect(screen.getByText(/does not load\s+them yet/)).toBeInTheDocument()
  })

  it('saves edited thresholds with every parameter, as numbers', async () => {
    const calls = stubApi()
    renderAt(`/settings?config=${DOS_ID}`)

    const threshold = await screen.findByLabelText('connections_to_target_threshold')
    await userEvent.clear(threshold)
    await userEvent.type(threshold, '150')
    await userEvent.selectOptions(screen.getByLabelText('window_s'), '10')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    await screen.findByText('Saved.')
    const patch = calls.find((c) => c.method === 'PATCH')
    expect(patch?.url).toBe(`/api/v1/detection-configurations/${DOS_ID}`)
    expect(patch?.body).toEqual({
      parameters: { window_s: 10, connections_to_target_threshold: 150, services: [22, 3389] },
    })
  })

  it('does not send a value that is not a number', async () => {
    const calls = stubApi()
    renderAt(`/settings?config=${PORT_SCAN_ID}`)

    const threshold = await screen.findByLabelText('unique_dst_ports_threshold')
    await userEvent.clear(threshold)
    await userEvent.type(threshold, '2.5')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Enter a whole number.')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'PATCH')).toBe(false)
  })

  it('shows the validation errors the API returns', async () => {
    stubApi({ writeStatus: 422, writeDetail: [{ loc: ['body', 'parameters', 'x'], msg: 'bad text' }] })
    renderAt(`/settings?config=${PORT_SCAN_ID}`)

    const threshold = await screen.findByLabelText('unique_dst_ports_threshold')
    await userEvent.type(threshold, '0')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('parameters.x: bad text')).toBeInTheDocument()
  })

  it('activates an inactive configuration, but only after the changes are saved', async () => {
    const calls = stubApi()
    renderAt(`/settings?config=${DOS_ID}`)

    const activate = await screen.findByRole('button', { name: 'Activate' })
    await userEvent.type(screen.getByLabelText('connections_to_target_threshold'), '0')
    expect(activate).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByTestId('search')).toHaveTextContent('')

    await userEvent.click(screen.getByRole('link', { name: /Edit DoS/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Activate' }))

    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(calls.find((c) => c.method === 'PUT')?.url).toBe(`/api/v1/detection-configurations/${DOS_ID}/activate`)
    const form = screen.getByRole('form', { name: /DoS/ })
    expect(await within(form).findByText('Active')).toBeInTheDocument()
    expect(within(form).queryByRole('button', { name: 'Activate' })).not.toBeInTheDocument()
  })

  it('creates a new inactive configuration with added parameters', async () => {
    const calls = stubApi()
    renderAt('/settings')

    await userEvent.click(await screen.findByRole('button', { name: 'New configuration' }))
    await userEvent.selectOptions(screen.getByLabelText('Type'), 'brute_force')
    await userEvent.type(screen.getByLabelText('New parameter'), 'attempts_same_service_threshold')
    await userEvent.type(screen.getByLabelText('Value'), '40')
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))
    await userEvent.type(screen.getByLabelText('New parameter'), 'services')
    await userEvent.type(screen.getByLabelText('Value'), '[[22, 21]')
    await userEvent.click(screen.getByRole('button', { name: 'Add' }))
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))

    await waitFor(() => expect(screen.getByTestId('search')).toHaveTextContent(`?config=${NEW_ID}`))
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      detection_type: 'brute_force',
      method: 'rule',
      parameters: { attempts_same_service_threshold: 40, services: [22, 21] },
    })
    expect(await screen.findByRole('button', { name: 'Activate' })).toBeInTheDocument()
  })

  it('is read-only for users without the admin role', async () => {
    stubApi()
    renderAt(`/settings?config=${PORT_SCAN_ID}`, 'user')

    expect(await screen.findByLabelText('unique_dst_ports_threshold')).toBeDisabled()
    expect(screen.getByRole('link', { name: /View Port Scan/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'New configuration' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('New parameter')).not.toBeInTheDocument()
  })

  it('says so when the configuration in the URL does not exist', async () => {
    stubApi()
    renderAt('/settings?config=10000000-0000-0000-0000-00000000dead')

    expect(await screen.findByText('Configuration not found.')).toBeInTheDocument()
  })
})
