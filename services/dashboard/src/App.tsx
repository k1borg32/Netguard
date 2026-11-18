import { Navigate, Route, Routes } from 'react-router'
import { LoginPage } from './auth/LoginPage'
import { RequireAuth } from './auth/RequireAuth'
import { Layout } from './components/Layout'
import { AlertDetailsPage } from './pages/AlertDetailsPage'
import { AlertsPage } from './pages/AlertsPage'
import { DetectionDetailsPage } from './pages/DetectionDetailsPage'
import { FlowDetailsPage } from './pages/FlowDetailsPage'
import { FlowsPage } from './pages/FlowsPage'
import { HistoryPage } from './pages/HistoryPage'
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
        <Route path="history" element={<HistoryPage />} />
        <Route path="history/:id" element={<DetectionDetailsPage />} />
        <Route path="flows" element={<FlowsPage />} />
        <Route path="flows/:id" element={<FlowDetailsPage />} />
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
