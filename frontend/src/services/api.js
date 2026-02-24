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

export async function fetchIncidents({ state, severity, alertType, limit = 50, cursor, offset = 0 } = {}) {
  const params = { limit }
  if (state) params.state = state
  if (severity) params.severity = severity
  if (alertType) params.alert_type = alertType
  if (cursor) params.cursor = cursor
  else if (offset) params.offset = offset
  const res = await api.get('/incidents/', { params })
  return res.data
}

export async function fetchIncident(id) {
  const res = await api.get(`/incidents/${id}/`)
  return res.data
}

export async function approveIncident(id, action, idempotencyKey) {
  const res = await api.post(`/incidents/${id}/approve/`, {
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
  const res = await api.post(`/incidents/${id}/reject/`, payload)
  return res.data
}

export default api
