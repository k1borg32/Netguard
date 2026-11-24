import { useEffect, useRef } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
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
  const { pathname } = useLocation()
  const main = useRef<HTMLElement>(null)
  const shownPath = useRef(pathname)

  // After moving to another screen, keyboard and screen reader users start at its content, not at the menu link
  // they used. Filter changes keep the path, so they don't move the focus.
  useEffect(() => {
    if (shownPath.current === pathname) return
    shownPath.current = pathname
    main.current?.focus()
  }, [pathname])

  return (
    <div className="shell">
      <a
        className="skip-link"
        href="#main"
        onClick={(e) => {
          e.preventDefault()
          main.current?.focus()
        }}
      >
        Skip to content
      </a>
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
      <main id="main" className="content" ref={main} tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
