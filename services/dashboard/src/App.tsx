import { Navigate, Route, Routes } from 'react-router'
import { LoginPage } from './auth/LoginPage'
import { RequireAuth } from './auth/RequireAuth'
import { Layout } from './components/Layout'
import { AlertDetailsPage } from './pages/AlertDetailsPage'
import { AlertsPage } from './pages/AlertsPage'
import { OverviewPage } from './pages/OverviewPage'
import { PlannedPage } from './pages/PlannedPage'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<OverviewPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="alerts/:id" element={<AlertDetailsPage />} />
        <Route
          path="history"
          element={
            <PlannedPage title="Detection history" week={6}>
              All stored detections with filters by time, type, severity and source.
            </PlannedPage>
          }
        />
        <Route
          path="flows"
          element={
            <PlannedPage title="Network flows" week={6}>
              Normalised flows with filters and paging.
            </PlannedPage>
          }
        />
        <Route
          path="settings"
          element={
            <PlannedPage title="Settings" week={7}>
              Detection thresholds (admin only).
            </PlannedPage>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
