import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { ToastProvider } from './context/ToastContext'
import { AuthProvider } from './context/AuthContext'
import Layout from './components/layout/Layout'
import PrivateRoute from './components/common/PrivateRoute'
import RequireRole from './components/common/RequireRole'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import IncidentDetail from './pages/IncidentDetail'
import AlertsPage from './pages/AlertsPage'
import ProactiveAlertsPage from './pages/ProactiveAlertsPage'
import RejectedPage from './pages/RejectedPage'
import DashboardPage from './pages/DashboardPage'
import LiveFeed from './pages/LiveFeed'
import SettingsPage from './pages/SettingsPage'
import UserManagementPage from './pages/UserManagementPage'
import HealthChecksPage from './pages/HealthChecksPage'
import SetPasswordPage from './pages/SetPasswordPage'
import NotFoundPage from './pages/NotFoundPage'
import AnalyticsPage from './pages/AnalyticsPage'
import KnowledgeBasePage from './pages/KnowledgeBasePage'
import ReportsPage from './pages/ReportsPage'

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/set-password" element={<SetPasswordPage />} />
              <Route path="/*" element={
                <PrivateRoute>
                  <Layout>
                    <Routes>
                      <Route path="/incidents" element={<Navigate to="/alerts" replace />} />
                      <Route path="/dashboard" element={<DashboardPage />} />
                      <Route path="/incidents/:id" element={<IncidentDetail />} />
                      <Route path="/alerts" element={<AlertsPage />} />
                      <Route path="/proactive" element={<ProactiveAlertsPage />} />
                      <Route path="/rejected" element={<RejectedPage />} />
                      <Route path="/live" element={<LiveFeed />} />
                      <Route path="/settings" element={<SettingsPage />} />
                      <Route path="/analytics" element={<AnalyticsPage />} />
                      <Route path="/knowledge-base" element={<KnowledgeBasePage />
        <Route path="/reports" element={<PrivateRoute><ReportsPage /></PrivateRoute>} />
} />
                      <Route path="/health-checks" element={<HealthChecksPage />} />
                      <Route path="/admin/users" element={
                        <RequireRole roles="admin">
                          <UserManagementPage />
                        </RequireRole>
                      } />
                      <Route path="*" element={<NotFoundPage />} />
                    </Routes>
                  </Layout>
                </PrivateRoute>
              } />
            </Routes>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}
