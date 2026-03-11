import axios from 'axios'

import {
  clearAccessToken,
  getRefreshToken,
  getValidAccessToken,
  setTokens,
} from './tokenStorage'

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
        }
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

export async function fetchIncident(id) {
  const res = await api.get(`/incidents/${id}`)
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
  const res = await api.get(`/users/${id}/`)
  return res.data
}

export async function createUser(data) {
  const res = await api.post('/users/', data)
  return res.data
}

export async function updateUser(id, data) {
  const res = await api.patch(`/users/${id}/`, data)
  return res.data
}

export async function deleteUser(id) {
  await api.delete(`/users/${id}/`)
}

export async function resendInvitation(userId) {
  const res = await api.post(`/users/${userId}/resend-invitation`)
  return res.data
}

// Metrics
export async function fetchMetrics() {
  const res = await api.get('/metrics/')
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

// Soft delete
export async function deleteIncident(incidentId) {
  await api.delete(`/incidents/${incidentId}`)
}

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

export default api
