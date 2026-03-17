import axios from 'axios'

import {
  clearAccessToken,
  getRefreshToken,
  getValidAccessToken,
  setTokens,
} from './tokenStorage'

const ACTIVE_TENANT_KEY = 'airex-active-tenant-id'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

function getCsrfToken() {
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(/(?:^|; )airex_csrf=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

/** Inject auth token or tenant header on every request. */
api.interceptors.request.use((config) => {
  const token = getValidAccessToken(5000)
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  } else {
    clearAccessToken()
    delete config.headers['Authorization']
  }
  const csrf = getCsrfToken()
  if (csrf) {
    config.headers['X-CSRF-Token'] = csrf
  }
  const activeTenantId = typeof window !== 'undefined' ? localStorage.getItem(ACTIVE_TENANT_KEY) : null
  if (activeTenantId) {
    config.headers['X-Active-Tenant-Id'] = activeTenantId
  }
  return config
})

/** Auto-refresh on 401 responses. */
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refreshToken = getRefreshToken()
      if (refreshToken) {
        try {
          const res = await axios.post('/api/v1/auth/refresh', {
            refresh_token: refreshToken,
          })
          setTokens({ accessToken: res.data.access_token, expiresIn: res.data.expires_in })
          original.headers['Authorization'] = `Bearer ${res.data.access_token}`
          return api(original)
        } catch {
          clearAccessToken()
          localStorage.removeItem('airex-refresh-token')
          window.dispatchEvent(new Event('session-expired'))
        }
      } else {
        clearAccessToken()
        window.dispatchEvent(new Event('session-expired'))
      }
    }
    return Promise.reject(error)
  }
)

export async function fetchIncidents({ state, severity, alertType, search, host_key, limit = 50, cursor, offset = 0 } = {}) {
  const params = { limit }
  if (state) params.state = state
  if (severity) params.severity = severity
  if (alertType) params.alert_type = alertType
  if (search && search.trim()) params.search = search.trim()
  if (host_key) params.host_key = host_key
  if (cursor) params.cursor = cursor
  else if (offset) params.offset = offset
  const res = await api.get('/incidents/', { params })
  return res.data
}

export function getActiveTenantId() {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(ACTIVE_TENANT_KEY)
}

export function setActiveTenantId(tenantId) {
  if (typeof window === 'undefined') return
  if (tenantId) localStorage.setItem(ACTIVE_TENANT_KEY, tenantId)
  else localStorage.removeItem(ACTIVE_TENANT_KEY)
}

export async function fetchAuthMe(tenantId = null) {
  const headers = {}
  const resolvedTenantId = tenantId || getActiveTenantId()
  if (resolvedTenantId) {
    headers['X-Active-Tenant-Id'] = resolvedTenantId
  }
  const res = await api.get('/auth/me', { headers })
  return res.data
}

export async function fetchIncident(id) {
  const res = await api.get(`/incidents/${id}`)
  return res.data
}

export async function createIncident(data, templateId = null) {
  const params = templateId ? { template_id: templateId } : {}
  const res = await api.post('/incidents/', data, { params })
  return res.data
}

export async function approveIncident(id, action, idempotencyKey) {
  const res = await api.post(`/incidents/${id}/approve`, {
    action,
    idempotency_key: idempotencyKey,
  })
  return res.data
}

export async function rejectIncident(id, reason) {
  const payload = {}
  if (reason && reason.trim()) {
    payload.reason = reason.trim()
  }
  const res = await api.post(`/incidents/${id}/reject`, payload)
  return res.data
}

// User management (admin only)
export async function fetchUsers({ limit = 100, offset = 0 } = {}) {
  const res = await api.get('/users/', { params: { limit, offset } })
  return res.data
}

export async function fetchUser(id) {
  const res = await api.get(`/users/${id}`)
  return res.data
}

export async function createUser(data) {
  const res = await api.post('/users/', data)
  return res.data
}

export async function updateUser(id, data) {
  const res = await api.patch(`/users/${id}`, data)
  return res.data
}

export async function deleteUser(id) {
  await api.delete(`/users/${id}`)
}

export async function resendInvitation(userId) {
  const res = await api.post(`/users/${userId}/resend-invitation`)
  return res.data
}

// Acknowledge incident
export async function acknowledgeIncident(id) {
  const res = await api.post(`/incidents/${id}/acknowledge`)
  return res.data
}

// Metrics
export async function fetchMetrics() {
  const res = await api.get('/metrics/')
  return res.data
}

// Tenants
export async function fetchTenants() {
  const res = await api.get('/tenants/')
  return res.data
}

export async function fetchOrganizations() {
  const res = await api.get('/organizations')
  return res.data
}

export async function createOrganization(data) {
  const res = await api.post('/organizations', data)
  return res.data
}

export async function updateOrganization(organizationId, data) {
  const res = await api.put(`/organizations/${organizationId}`, data)
  return res.data
}

export async function fetchOrganizationTenants(organizationId) {
  const res = await api.get(`/organizations/${organizationId}/tenants`)
  return res.data
}

export async function fetchOrganizationAnalytics(organizationId) {
  const res = await api.get(`/organizations/${organizationId}/analytics`)
  return res.data
}

// Org member management
export async function fetchOrgMembers(organizationId) {
  const res = await api.get(`/organizations/${organizationId}/members`)
  return res.data
}

export async function addOrgMember(organizationId, data) {
  const res = await api.post(`/organizations/${organizationId}/members`, data)
  return res.data
}

export async function updateOrgMember(organizationId, userId, data) {
  const res = await api.patch(`/organizations/${organizationId}/members/${userId}`, data)
  return res.data
}

export async function removeOrgMember(organizationId, userId) {
  await api.delete(`/organizations/${organizationId}/members/${userId}`)
}

// Tenant member management
export async function fetchTenantMembers(tenantId) {
  const res = await api.get(`/tenants/${tenantId}/members`)
  return res.data
}

export async function addTenantMember(tenantId, data) {
  const res = await api.post(`/tenants/${tenantId}/members`, data)
  return res.data
}

export async function updateTenantMember(tenantId, userId, data) {
  const res = await api.patch(`/tenants/${tenantId}/members/${userId}`, data)
  return res.data
}

export async function removeTenantMember(tenantId, userId) {
  await api.delete(`/tenants/${tenantId}/members/${userId}`)
}

// User accessible tenants
export async function fetchUserAccessibleTenants(userId) {
  const res = await api.get(`/users/${userId}/accessible-tenants`)
  return res.data
}

export async function createOrganizationTenant(organizationId, data) {
  const res = await api.post(`/organizations/${organizationId}/tenants`, data)
  return res.data
}

export async function fetchProjects(tenantId) {
  const res = await api.get(`/tenants/${tenantId}/projects`)
  return res.data
}

export async function createProject(tenantId, data) {
  const res = await api.post(`/tenants/${tenantId}/projects`, data)
  return res.data
}

export async function updateProject(projectId, data) {
  const res = await api.put(`/projects/${projectId}`, data)
  return res.data
}

export async function deleteProject(projectId) {
  await api.delete(`/projects/${projectId}`)
}

export async function fetchIntegrationTypes() {
  const res = await api.get('/integration-types')
  return res.data
}

export async function fetchIntegrations(tenantId) {
  const res = await api.get(`/tenants/${tenantId}/integrations`)
  return res.data
}

export async function createIntegration(tenantId, data) {
  const res = await api.post(`/tenants/${tenantId}/integrations`, data)
  return res.data
}

export async function updateIntegration(integrationId, data) {
  const res = await api.put(`/integrations/${integrationId}`, data)
  return res.data
}

export async function deleteIntegration(integrationId) {
  const res = await api.delete(`/integrations/${integrationId}`)
  return res.data
}

export async function testIntegration(integrationId) {
  const res = await api.post(`/integrations/${integrationId}/test`)
  return res.data
}

export async function syncIntegrationMonitors(integrationId, monitors = []) {
  const res = await api.post(`/integrations/${integrationId}/sync-monitors`, { monitors })
  return res.data
}

export async function fetchExternalMonitors(integrationId) {
  const res = await api.get(`/integrations/${integrationId}/external-monitors`)
  return res.data
}

export async function fetchProjectMonitorBindings(projectId) {
  const res = await api.get(`/projects/${projectId}/monitor-bindings`)
  return res.data
}

export async function createProjectMonitorBinding(projectId, data) {
  const res = await api.post(`/projects/${projectId}/monitor-bindings`, data)
  return res.data
}

export async function deleteProjectMonitorBinding(bindingId) {
  const res = await api.delete(`/project-monitor-bindings/${bindingId}`)
  return res.data
}

export async function fetchTenantDetail(name) {
  const res = await api.get(`/tenants/${encodeURIComponent(name)}`)
  return res.data
}

export async function createTenant(data) {
  const res = await api.post('/tenants/', data)
  return res.data
}

export async function updateTenant(name, data) {
  const res = await api.put(`/tenants/${encodeURIComponent(name)}`, data)
  return res.data
}

export async function deleteTenant(name) {
  const res = await api.delete(`/tenants/${encodeURIComponent(name)}`)
  return res.data
}

export async function reloadTenants() {
  const res = await api.post('/tenants/reload')
  return res.data
}

// DLQ (admin only)
export async function fetchDLQ({ limit = 100, offset = 0 } = {}) {
  const res = await api.get('/dlq/', { params: { limit, offset } })
  return res.data
}

export async function replayDLQEntry(entryIndex) {
  const res = await api.post(`/dlq/${entryIndex}/replay`)
  return res.data
}

export async function clearDLQ() {
  const res = await api.delete('/dlq/')
  return res.data
}

// Incident soft delete
export async function deleteIncident(id) {
  await api.delete(`/incidents/${id}`)
}

// Incident AI Chat
export async function sendChatMessage(incidentId, message) {
  const res = await api.post(`/incidents/${incidentId}/chat`, { message })
  return res.data
}

export async function fetchChatHistory(incidentId) {
  const res = await api.get(`/incidents/${incidentId}/chat/history`)
  return res.data
}

export async function clearChatHistory(incidentId) {
  await api.delete(`/incidents/${incidentId}/chat/history`)
}

// Settings (admin only)
export async function fetchSettings() {
  const res = await api.get('/settings/')
  return res.data
}

export async function updateSettings(data) {
  const res = await api.patch('/settings/', data)
  return res.data
}

export async function fetchBackendHealth() {
  const res = await axios.get('/health', { withCredentials: true })
  return res.data
}

// Incident feedback (operator rating)
export async function submitFeedback(incidentId, score, note) {
  const payload = { score }
  if (note && note.trim()) {
    payload.note = note.trim()
  }
  const res = await api.post(`/incidents/${incidentId}/feedback`, payload)
  return res.data
}

export async function fetchAutoRunbook(incidentId) {
  const res = await api.get(`/incidents/${incidentId}/runbook`)
  return res.data
}

// Comments
export async function fetchComments(incidentId) {
  const res = await api.get(`/incidents/${incidentId}/comments`)
  return res.data
}

export async function createComment(incidentId, content) {
  const res = await api.post(`/incidents/${incidentId}/comments`, { content })
  return res.data
}

// Assignment
export async function assignIncident(incidentId, userId) {
  const res = await api.post(`/incidents/${incidentId}/assign`, { assigned_to: userId })
  return res.data
}

export async function unassignIncident(incidentId) {
  const res = await api.post(`/incidents/${incidentId}/assign`, { assigned_to: null })
  return res.data
}

// Bulk operations
export async function bulkApprove(incidentIds, reason) {
  const res = await api.post('/incidents/bulk-approve', { incident_ids: incidentIds, reason })
  return res.data
}

export async function bulkReject(incidentIds, reason) {
  const res = await api.post('/incidents/bulk-reject', { incident_ids: incidentIds, reason })
  return res.data
}

// Export
export async function exportIncidents(format = 'json', filters = {}) {
  const params = { format, ...filters }
  const res = await api.get('/incidents/export', { params, responseType: 'blob' })
  return res.data
}

// Restore
export async function restoreIncident(incidentId) {
  const res = await api.post(`/incidents/${incidentId}/restore`)
  return res.data
}

// Health checks (Phase 6 ARE — Proactive Monitoring)
export async function fetchHealthCheckDashboard() {
  const res = await api.get('/health-checks/dashboard')
  return res.data
}

export async function fetchTargetHistory(targetType, targetId, { limit = 100 } = {}) {
  const res = await api.get(`/health-checks/targets/${targetType}/${targetId}/history`, { params: { limit } })
  return res.data
}

export async function triggerHealthCheck() {
  const res = await api.post('/health-checks/run')
  return res.data
}

export async function fetchMonitorInventory({ refresh = false } = {}) {
  const res = await api.get('/health-checks/monitors', { params: refresh ? { refresh: true } : {} })
  return res.data
}

// Alert history widget (7-day degraded/down counts from health_checks)
export async function fetchAlertHistory({ days = 7 } = {}) {
  const res = await api.get('/metrics/alert-history', { params: { days } })
  return res.data
}

// Analytics trends
export async function fetchAnalyticsTrends(days = 30) {
  const res = await api.get('/analytics/trends', { params: { days } })
  return res.data
}

// Related incidents
export async function fetchRelatedIncidents(incidentId) {
  const res = await api.get(`/incidents/${incidentId}/related`)
  return res.data
}

export async function linkIncident(incidentId, relatedIncidentId, relationshipType = 'related', note = null) {
  const res = await api.post(`/incidents/${incidentId}/related`, {
    related_incident_id: relatedIncidentId,
    relationship_type: relationshipType,
    note,
  })
  return res.data
}

export async function unlinkIncident(incidentId, relatedIncidentId) {
  await api.delete(`/incidents/${incidentId}/related/${relatedIncidentId}`)
}

// Incident templates
export async function fetchTemplates(activeOnly = false) {
  const res = await api.get('/templates', { params: { active_only: activeOnly } })
  return res.data
}

export async function getTemplate(templateId) {
  const res = await api.get(`/templates/${templateId}`)
  return res.data
}

export async function createTemplate(data) {
  const res = await api.post('/templates', data)
  return res.data
}

export async function updateTemplate(templateId, data) {
  const res = await api.put(`/templates/${templateId}`, data)
  return res.data
}

export async function deleteTemplate(templateId) {
  await api.delete(`/templates/${templateId}`)
}

// Knowledge base
export async function fetchKnowledgeBase(params = {}) {
  const res = await api.get('/knowledge-base', { params })
  return res.data
}

export async function getKnowledgeBaseEntry(entryId) {
  const res = await api.get(`/knowledge-base/${entryId}`)
  return res.data
}

export async function createKnowledgeBaseEntry(data) {
  const res = await api.post('/knowledge-base', data)
  return res.data
}

export async function updateKnowledgeBaseEntry(entryId, data) {
  const res = await api.put(`/knowledge-base/${entryId}`, data)
  return res.data
}

export async function deleteKnowledgeBaseEntry(entryId) {
  await api.delete(`/knowledge-base/${entryId}`)
}

// Report templates
export async function fetchReports(activeOnly = false) {
  const res = await api.get('/reports', { params: { active_only: activeOnly } })
  return res.data
}

export async function getReport(templateId) {
  const res = await api.get(`/reports/${templateId}`)
  return res.data
}

export async function createReport(data) {
  const res = await api.post('/reports', data)
  return res.data
}

export async function updateReport(templateId, data) {
  const res = await api.put(`/reports/${templateId}`, data)
  return res.data
}

export async function deleteReport(templateId) {
  await api.delete(`/reports/${templateId}`)
}

export async function generateReport(templateId) {
  const res = await api.post(`/reports/${templateId}/generate`)
  return res.data
}

// Patterns
export async function fetchPatterns(windowDays = 30) {
  const res = await api.get('/patterns', { params: { window_days: windowDays } })
  return res.data
}

export async function getPattern(patternId) {
  const res = await api.get(`/patterns/${patternId}`)
  return res.data
}

// Predictions
export async function predictRootCause(alertType, severity = null, hostKey = null) {
  const params = { alert_type: alertType }
  if (severity) params.severity = severity
  if (hostKey) params.host_key = hostKey
  const res = await api.get('/predictions/root-cause', { params })
  return res.data
}

export async function getPredictionAccuracy(days = 30) {
  const res = await api.get('/predictions/accuracy', { params: { days } })
  return res.data
}

// Anomalies
export async function fetchAnomalies(baselineDays = 30, windowHours = 24) {
  const res = await api.get('/anomalies', { params: { baseline_days: baselineDays, detection_window_hours: windowHours } })
  return res.data
}

// Runbooks
export async function fetchRunbooks(activeOnly = false, alertType = null) {
  const params = {}
  if (activeOnly) params.active_only = true
  if (alertType) params.alert_type = alertType
  const res = await api.get('/runbooks', { params })
  return res.data
}

export async function getRunbook(runbookId) {
  const res = await api.get(`/runbooks/${runbookId}`)
  return res.data
}

export async function createRunbook(data) {
  const res = await api.post('/runbooks', data)
  return res.data
}

export async function updateRunbook(runbookId, data) {
  const res = await api.put(`/runbooks/${runbookId}`, data)
  return res.data
}

export async function deleteRunbook(runbookId) {
  await api.delete(`/runbooks/${runbookId}`)
}

export async function duplicateRunbook(runbookId) {
  const res = await api.post(`/runbooks/${runbookId}/duplicate`)
  return res.data
}

// Grafana Dashboards
export async function fetchGrafanaTemplates(category = null) {
  const params = category ? { category } : {}
  const res = await api.get('/grafana-dashboards/templates', { params })
  return res.data
}


// Notification preferences
export async function fetchNotificationPreferences() {
  const res = await api.get('/notification-preferences/me')
  return res.data
}

export async function updateNotificationPreferences(data) {
  const res = await api.put('/notification-preferences/me', data)
  return res.data
}

export default api
