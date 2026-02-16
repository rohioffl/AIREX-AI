/**
 * SSE connection manager with auto-reconnect (exponential backoff + jitter).
 *
 * Subscribes to the tenant event stream. All UI state updates
 * come from SSE — never simulate transitions locally.
 *
 * Auth: passes JWT token as query param if available (EventSource
 * API does not support custom headers). Falls back to tenant ID.
 */

const MAX_RETRY_DELAY = 30000
const INITIAL_RETRY_DELAY = 1000
const MAX_JITTER = 500

export function createSSEConnection(tenantId, handlers, onConnectionChange) {
  let eventSource = null
  let retryDelay = INITIAL_RETRY_DELAY
  let closed = false
  let retryCount = 0

  function connect() {
    if (closed) return

    const token = localStorage.getItem('airex-token')
    const params = new URLSearchParams()

    if (token) {
      params.set('token', token)
    } else {
      params.set('x_tenant_id', tenantId)
    }

    const url = `/api/v1/events/stream?${params.toString()}`
    eventSource = new EventSource(url)

    eventSource.onopen = () => {
      retryDelay = INITIAL_RETRY_DELAY
      retryCount = 0
      onConnectionChange?.({ connected: true, retrying: false, retryCount: 0 })
    }

    eventSource.onerror = () => {
      eventSource.close()
      retryCount++
      onConnectionChange?.({ connected: false, retrying: true, retryCount })

      if (!closed) {
        const jitter = Math.random() * MAX_JITTER
        const delay = Math.min(retryDelay + jitter, MAX_RETRY_DELAY)

        setTimeout(() => {
          retryDelay = Math.min(retryDelay * 2, MAX_RETRY_DELAY)
          connect()
        }, delay)
      }
    }

    // Register event handlers
    const eventTypes = [
      'incident_created',
      'state_changed',
      'evidence_added',
      'recommendation_ready',
      'execution_started',
      'execution_log',
      'execution_completed',
      'verification_result',
    ]

    eventTypes.forEach((type) => {
      eventSource.addEventListener(type, (event) => {
        try {
          const data = JSON.parse(event.data)
          handlers[type]?.(data)
        } catch {
          // Ignore parse errors
        }
      })
    })

    // Ignore heartbeats silently
    eventSource.addEventListener('heartbeat', () => {})
  }

  connect()

  return {
    close() {
      closed = true
      eventSource?.close()
      onConnectionChange?.({ connected: false, retrying: false, retryCount })
    },
  }
}
