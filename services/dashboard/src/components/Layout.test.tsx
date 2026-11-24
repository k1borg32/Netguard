import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthState } from '../auth/context'
import { usePageTitle } from '../lib/usePageTitle'
import { Layout } from './Layout'

function Page({ title }: { title: string }) {
  usePageTitle(title)
  return <h1>{title}</h1>
}

const auth: AuthState = {
  status: 'authenticated',
  user: { user_id: 'u1', username: 'admin', role: 'admin' },
  expired: false,
  login: async () => {},
  logout: async () => {},
}

function renderShell() {
  // The health pill polls /health; an answer that never comes is enough here.
  vi.stubGlobal(
    'fetch',
    vi.fn(() => new Promise<Response>(() => {})),
  )
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthContext.Provider value={auth}>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Page title="Overview" />} />
              <Route path="alerts" element={<Page title="Alerts" />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
}

describe('Layout (keyboard and screen reader use)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('gives every screen its own title', async () => {
    renderShell()
    expect(document.title).toBe('Overview · NetGuard')
    await userEvent.click(screen.getByRole('link', { name: 'Alerts' }))
    expect(document.title).toBe('Alerts · NetGuard')
  })

  it('starts with a skip link that jumps to the content', async () => {
    renderShell()
    await userEvent.tab()
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    expect(screen.getByRole('main')).toHaveFocus()
  })

  it('moves the focus to the new screen after using the menu, not on the first load', async () => {
    renderShell()
    expect(screen.getByRole('main')).not.toHaveFocus()
    await userEvent.click(screen.getByRole('link', { name: 'Alerts' }))
    expect(screen.getByRole('main')).toHaveFocus()
    expect(screen.getByRole('link', { name: 'Alerts' })).toHaveAttribute('aria-current', 'page')
  })
})
