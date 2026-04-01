import { BrowserRouter, Routes, Route, Navigate, useParams, useLocation } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { ToastProvider } from './context/ToastContext'
import { AuthProvider } from './context/AuthContext'
import { getActiveOrganizationIdOverride } from './utils/organizationScope'
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
import SetPasswordPage from './pages/SetPasswordPage'
import AcceptInvitationPage from './pages/AcceptInvitationPage'
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
import CloudAccountsPage from './pages/admin/CloudAccountsPage'
import PlatformAdminPage from './pages/PlatformAdminPage'
import { useAuth } from './context/AuthContext'

/**
 * Redirects legacy flat paths to the correct workspace-scoped path.
 * Org users → /:orgSlug/page  (no tenant slug)
 * Tenant users → /:orgSlug/:tenantSlug/page
 */
function WorkspaceRedirect({ page }) {
  const { activeTenant, activeOrganization, loading, organizationMemberships, user } = useAuth()
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
      </div>
    )
  }
  const orgSlug = activeOrganization?.slug || activeOrganization?.id
  const tenantSlug = activeTenant?.name || activeTenant?.id
  const role = user?.role?.toLowerCase()
  const isOrgUser =
    organizationMemberships?.length > 0 ||
    role === 'admin' ||
    role === 'platform_admin'

  if (isOrgUser && orgSlug) return <Navigate to={`/${orgSlug}/${page}`} replace />
  if (!orgSlug || !tenantSlug) return <Navigate to="/login" replace />
  return <Navigate to={`/${orgSlug}/${tenantSlug}/${page}`} replace />
}

/**
 * Redirects legacy /incidents/:id (with optional ?tenant_id=) to the
 * workspace-scoped incident detail path, preserving the tenant_id query param.
 */
function IncidentRedirect() {
  const { id } = useParams()
  const location = useLocation()
  const tenantId = new URLSearchParams(location.search).get('tenant_id')
  const suffix = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : ''
  return <WorkspaceRedirect page={`incidents/${id}${suffix}`} />
}

function OrganizationScopedRedirect({ destination = 'organization' }) {
  const auth = useAuth()
  const activeOrganization = auth.organizations?.find(
    (organization) => String(organization.id) === String(getActiveOrganizationIdOverride())
  ) || auth.activeOrganization || auth.organizations?.[0] || null
  const organizationKey = activeOrganization?.slug || activeOrganization?.id || ''

  if (!organizationKey) {
    return <Navigate to="/dashboard" replace />
  }

  const target = destination === 'workspaces'
    ? `/admin/organizations/${encodeURIComponent(organizationKey)}/workspaces`
    : `/admin/organizations/${encodeURIComponent(organizationKey)}`

  return <Navigate to={target} replace />
}


export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <Routes>
              {/* Public routes */}
              <Route path="/" element={<ErrorBoundary><LandingPage /></ErrorBoundary>} />
              <Route path="/login" element={<ErrorBoundary><LoginPage /></ErrorBoundary>} />
              <Route path="/admin/login" element={<ErrorBoundary><AdminLoginPage /></ErrorBoundary>} />
              <Route path="/set-password" element={<ErrorBoundary><SetPasswordPage /></ErrorBoundary>} />
              <Route path="/accept-invitation" element={<ErrorBoundary><AcceptInvitationPage /></ErrorBoundary>} />

              {/* Platform admin (no Layout wrapper) */}
              <Route path="/admin" element={
                <PrivateRoute>
                  <RequireRole access="platform_admin">
                    <ErrorBoundary><PlatformAdminPage /></ErrorBoundary>
                  </RequireRole>
                </PrivateRoute>
              } />

              {/* All routes that need the Layout shell — pathless layout route */}
              <Route element={
                <PrivateRoute>
                  <ErrorBoundary>
                    <Layout />
                  </ErrorBoundary>
                </PrivateRoute>
              }>
                {/* Admin routes */}
                <Route path="/admin/organizations" element={
                  <RequireRole access="organizations_admin">
                    <OrganizationScopedRedirect />
                  </RequireRole>
                } />
                <Route path="/admin/organizations/:organizationSlug" element={
                  <RequireRole access="organizations_admin">
                    <ErrorBoundary><OrganizationsAdminPage /></ErrorBoundary>
                  </RequireRole>
                } />
                <Route path="/admin/workspaces" element={
                  <RequireRole access="tenant_admin">
                    <OrganizationScopedRedirect destination="workspaces" />
                  </RequireRole>
                } />
                <Route path="/admin/organizations/:organizationSlug/workspaces" element={
                  <RequireRole access="tenant_admin">
                    <ErrorBoundary><TenantWorkspaceAdminPage /></ErrorBoundary>
                  </RequireRole>
                } />
                <Route path="/admin/integrations" element={
                  <RequireRole access="tenant_admin">
                    <ErrorBoundary><IntegrationsAdminPage /></ErrorBoundary>
                  </RequireRole>
                } />
                <Route path="/admin/cloud-accounts" element={
                  <RequireRole access="tenant_admin">
                    <ErrorBoundary><CloudAccountsPage /></ErrorBoundary>
                  </RequireRole>
                } />

                {/* Org-scoped routes: /:orgSlug/:page  (org users — no tenant slug in URL) */}
                <Route path="/:orgSlug/dashboard" element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/alerts" element={<ErrorBoundary><AlertsPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/incidents/:id" element={<ErrorBoundary><IncidentDetail /></ErrorBoundary>} />
                <Route path="/:orgSlug/rejected" element={<ErrorBoundary><RejectedPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/live" element={<ErrorBoundary><LiveFeed /></ErrorBoundary>} />
                <Route path="/:orgSlug/settings" element={<ErrorBoundary><SettingsPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/analytics" element={<ErrorBoundary><AnalyticsPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/knowledge-base" element={<ErrorBoundary><KnowledgeBasePage /></ErrorBoundary>} />
                <Route path="/:orgSlug/reports" element={<ErrorBoundary><ReportsPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/runbooks" element={<ErrorBoundary><RunbooksPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/patterns" element={<ErrorBoundary><PatternsPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/profile" element={<ErrorBoundary><ProfilePage /></ErrorBoundary>} />

                {/* Tenant-scoped routes: /:orgSlug/:tenantSlug/:page  (tenant users) */}
                <Route path="/:orgSlug/:tenantSlug/dashboard" element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/alerts" element={<ErrorBoundary><AlertsPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/incidents/:id" element={<ErrorBoundary><IncidentDetail /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/rejected" element={<ErrorBoundary><RejectedPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/live" element={<ErrorBoundary><LiveFeed /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/settings" element={<ErrorBoundary><SettingsPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/analytics" element={<ErrorBoundary><AnalyticsPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/knowledge-base" element={<ErrorBoundary><KnowledgeBasePage /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/reports" element={<ErrorBoundary><ReportsPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/runbooks" element={<ErrorBoundary><RunbooksPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/patterns" element={<ErrorBoundary><PatternsPage /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/profile" element={<ErrorBoundary><ProfilePage /></ErrorBoundary>} />
                <Route path="/:orgSlug/:tenantSlug/org-admin" element={
                  <RequireRole access="organizations_admin">
                    <OrganizationScopedRedirect />
                  </RequireRole>
                } />
              </Route>

              {/* Legacy flat-path redirects → workspace-scoped equivalents */}
              <Route path="/dashboard" element={<PrivateRoute><WorkspaceRedirect page="dashboard" /></PrivateRoute>} />
              <Route path="/alerts" element={<PrivateRoute><WorkspaceRedirect page="alerts" /></PrivateRoute>} />
              <Route path="/incidents" element={<PrivateRoute><WorkspaceRedirect page="alerts" /></PrivateRoute>} />
              <Route path="/incidents/:id" element={<PrivateRoute><IncidentRedirect /></PrivateRoute>} />
              <Route path="/rejected" element={<PrivateRoute><WorkspaceRedirect page="rejected" /></PrivateRoute>} />
              <Route path="/live" element={<PrivateRoute><WorkspaceRedirect page="live" /></PrivateRoute>} />
              <Route path="/analytics" element={<PrivateRoute><WorkspaceRedirect page="analytics" /></PrivateRoute>} />
              <Route path="/knowledge-base" element={<PrivateRoute><WorkspaceRedirect page="knowledge-base" /></PrivateRoute>} />
              <Route path="/reports" element={<PrivateRoute><WorkspaceRedirect page="reports" /></PrivateRoute>} />
              <Route path="/runbooks" element={<PrivateRoute><WorkspaceRedirect page="runbooks" /></PrivateRoute>} />
              <Route path="/patterns" element={<PrivateRoute><WorkspaceRedirect page="patterns" /></PrivateRoute>} />
              <Route path="/settings" element={<PrivateRoute><WorkspaceRedirect page="settings" /></PrivateRoute>} />
              <Route path="/profile" element={<PrivateRoute><WorkspaceRedirect page="profile" /></PrivateRoute>} />
              <Route path="/org-settings" element={<PrivateRoute><WorkspaceRedirect page="dashboard" /></PrivateRoute>} />
              <Route path="/org-admin" element={<PrivateRoute><RequireRole access="organizations_admin"><OrganizationScopedRedirect /></RequireRole></PrivateRoute>} />

              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}
