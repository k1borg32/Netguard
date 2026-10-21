import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../api/client'
import { AuthContext, type AuthState } from './context'
import { LoginPage } from './LoginPage'

function renderLogin(auth: Partial<AuthState>) {
  const value: AuthState = {
    status: 'anonymous',
    user: null,
    expired: false,
    login: vi.fn(),
    logout: vi.fn(),
    ...auth,
  }
  render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<p>overview page</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
  return value
}

describe('LoginPage', () => {
  it('sends the trimmed username and the password', async () => {
    const auth = renderLogin({ login: vi.fn().mockResolvedValue(undefined) })

    await userEvent.type(screen.getByLabelText('Username'), ' admin ')
    await userEvent.type(screen.getByLabelText('Password'), 'correct horse battery')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(auth.login).toHaveBeenCalledWith('admin', 'correct horse battery')
  })

  it('shows an error for wrong credentials', async () => {
    renderLogin({ login: vi.fn().mockRejectedValue(new ApiError(401, 'Authentication failed')) })

    await userEvent.type(screen.getByLabelText('Username'), 'admin')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong username or password')
  })

  it('tells the user when the session expired', () => {
    renderLogin({ expired: true })
    expect(screen.getByText(/session expired/i)).toBeInTheDocument()
  })

  it('redirects to the overview when already signed in', () => {
    renderLogin({ status: 'authenticated' })
    expect(screen.getByText('overview page')).toBeInTheDocument()
  })
})
