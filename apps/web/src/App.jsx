import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { ToastProvider } from './context/ToastContext'
import { AuthProvider } from './context/AuthContext'
import Layout from './components/layout/Layout'
import PrivateRoute from './components/common/PrivateRoute'
import RequireRole from './components/common/RequireRole'
import ErrorBoundary from './components/common/ErrorBoundary'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import AdminLoginPage from './pages/AdminLoginPage'
import IncidentDetail from './pages/IncidentDetail'
import AlertsPage from './pages/AlertsPage'
import RejectedPage from './pages/RejectedPage'
import DashboardPage from './pages/DashboardPage'
import LiveFeed from './pages/LiveFeed'
import SettingsPage from './pages/SettingsPage'
import SuperAdminPage from './pages/SuperAdminPage'
import HealthChecksPage from './pages/HealthChecksPage'
import LiveMonitoringPage from './pages/LiveMonitoringPage'
import SetPasswordPage from './pages/SetPasswordPage'
import NotFoundPage from './pages/NotFoundPage'
import AnalyticsPage from './pages/AnalyticsPage'
import KnowledgeBasePage from './pages/KnowledgeBasePage'
import ReportsPage from './pages/ReportsPage'
import RunbooksPage from './pages/RunbooksPage'
import PatternsPage from './pages/PatternsPage'
import ProfilePage from './pages/ProfilePage'
import OrganizationsAdminPage from './pages/admin/OrganizationsAdminPage'
import TenantWorkspaceAdminPage from './pages/admin/TenantWorkspaceAdminPage'
import IntegrationsAdminPage from './pages/admin/IntegrationsAdminPage'
import PlatformAdminPage from './pages/PlatformAdminPage'
import OrgSettingsPage from './pages/OrgSettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <Routes>
              <Route path="/" element={<ErrorBoundary><LandingPage /></ErrorBoundary>} />
              <Route path="/login" element={<ErrorBoundary><LoginPage /></ErrorBoundary>} />
              <Route path="/admin/login" element={<ErrorBoundary><AdminLoginPage /></ErrorBoundary>} />
              <Route path="/set-password" element={<ErrorBoundary><SetPasswordPage /></ErrorBoundary>} />
              <Route path="/admin" element={
                <PrivateRoute>
                  <RequireRole access="platform_admin">
                    <ErrorBoundary><PlatformAdminPage /></ErrorBoundary>
                  </RequireRole>
                </PrivateRoute>
              } />
              <Route path="/*" element={
                <PrivateRoute>
                  <Layout>
                    <Routes>
                      <Route path="/incidents" element={<Navigate to="/alerts" replace />} />
                      <Route path="/dashboard" element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
                      <Route path="/incidents/:id" element={<ErrorBoundary><IncidentDetail /></ErrorBoundary>} />
                      <Route path="/alerts" element={<ErrorBoundary><AlertsPage /></ErrorBoundary>} />
                      <Route path="/proactive" element={<Navigate to="/health-checks/site24x7?tab=ai-alerts" replace />} />
                      <Route path="/rejected" element={<ErrorBoundary><RejectedPage /></ErrorBoundary>} />
                      <Route path="/live" element={<ErrorBoundary><LiveFeed /></ErrorBoundary>} />
                      <Route path="/settings" element={<ErrorBoundary><SettingsPage /></ErrorBoundary>} />
                      <Route path="/analytics" element={<ErrorBoundary><AnalyticsPage /></ErrorBoundary>} />
                      <Route path="/knowledge-base" element={<ErrorBoundary><KnowledgeBasePage /></ErrorBoundary>} />
                      <Route path="/reports" element={<ErrorBoundary><ReportsPage /></ErrorBoundary>} />
                      <Route path="/runbooks" element={<ErrorBoundary><RunbooksPage /></ErrorBoundary>} />
                      <Route path="/patterns" element={<ErrorBoundary><PatternsPage /></ErrorBoundary>} />
                      <Route path="/profile" element={<ErrorBoundary><ProfilePage /></ErrorBoundary>} />
                      <Route path="/org-settings" element={<ErrorBoundary><OrgSettingsPage /></ErrorBoundary>} />
                      <Route path="/health-checks" element={<ErrorBoundary><LiveMonitoringPage /></ErrorBoundary>} />
                      <Route path="/health-checks/site24x7" element={<ErrorBoundary><HealthChecksPage /></ErrorBoundary>} />
                      <Route path="/org-admin" element={
                        <RequireRole access="organizations_admin">
                          <ErrorBoundary><SuperAdminPage /></ErrorBoundary>
                        </RequireRole>
                      } />
                      <Route path="/admin/organizations" element={
                        <RequireRole access="organizations_admin">
                          <ErrorBoundary><OrganizationsAdminPage /></ErrorBoundary>
                        </RequireRole>
                      } />
                      <Route path="/admin/workspaces" element={
                        <RequireRole access="tenant_admin">
                          <ErrorBoundary><TenantWorkspaceAdminPage /></ErrorBoundary>
                        </RequireRole>
                      } />
                      <Route path="/admin/integrations" element={
                        <RequireRole access="tenant_admin">
                          <ErrorBoundary><IntegrationsAdminPage /></ErrorBoundary>
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
