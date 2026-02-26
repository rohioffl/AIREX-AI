import axios from 'axios'

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
  const token = localStorage.getItem('airex-token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
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
      const refreshToken = localStorage.getItem('airex-refresh-token')
      if (refreshToken) {
        try {
          const res = await axios.post('/api/v1/auth/refresh', {
            refresh_token: refreshToken,
          })
          localStorage.setItem('airex-token', res.data.access_token)
          original.headers['Authorization'] = `Bearer ${res.data.access_token}`
          return api(original)
        } catch {
          localStorage.removeItem('airex-token')
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

export default api
