import { NavLink, Outlet } from 'react-router'
import { useAuth } from '../auth/context'
import { HealthPill } from './HealthPill'

const NAV = [
  { to: '/', label: 'Overview' },
  { to: '/alerts', label: 'Alerts' },
  { to: '/history', label: 'History' },
  { to: '/flows', label: 'Flows' },
  { to: '/settings', label: 'Settings' },
]

export function Layout() {
  const { user, logout } = useAuth()
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true" />
          NetGuard
        </div>
        <div className="topbar-right">
          <HealthPill />
          <span className="user">
            {user?.username}
            {user?.role === 'admin' && <span className="muted small"> (admin)</span>}
          </span>
          <button className="link-button" type="button" onClick={() => void logout()}>
            Log out
          </button>
        </div>
      </header>
      <nav className="sidebar" aria-label="Main">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'} className="nav-item">
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
