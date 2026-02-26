/**
 * SSE connection manager with auto-reconnect (short delay, low latency).
 *
 * Subscribes to the tenant event stream. All UI state updates
 * come from SSE — never simulate transitions locally.
 *
 * Auth: passes JWT token as query param if available (EventSource
 * API does not support custom headers). Falls back to tenant ID.
 */

const MAX_RETRY_DELAY = 10000
const INITIAL_RETRY_DELAY = 300
const MAX_JITTER = 200
const STALE_THRESHOLD_MS = 45000

export function createSSEConnection(handlers, onConnectionChange) {
  let eventSource = null
  let retryDelay = INITIAL_RETRY_DELAY
  let closed = false
  let lastEventAt = 0
  let staleCheckInterval = null

  function connect() {
    if (closed) return

    const token = localStorage.getItem('airex-token')
    const params = new URLSearchParams()

    if (token) {
      params.set('token', token)
    }

    const url = `/api/v1/events/stream?${params.toString()}`
    eventSource = new EventSource(url)

    eventSource.onopen = () => {
      lastEventAt = Date.now()
      retryDelay = INITIAL_RETRY_DELAY
      onConnectionChange?.({ connected: true, retrying: false, initial: false })
      startStaleCheck()
    }

    eventSource.onerror = () => {
      stopStaleCheck()
      eventSource.close()
      eventSource = null
      onConnectionChange?.({ connected: false, retrying: true, initial: false })

      if (!closed) {
        const jitter = Math.random() * MAX_JITTER
        const delay = Math.min(retryDelay + jitter, MAX_RETRY_DELAY)

        setTimeout(() => {
          retryDelay = Math.min(retryDelay * 1.5, MAX_RETRY_DELAY)
          connect()
        }, delay)
      }
    }

    function markActivity() {
      lastEventAt = Date.now()
    }

    function startStaleCheck() {
      stopStaleCheck()
      staleCheckInterval = setInterval(() => {
        if (closed || !eventSource || eventSource.readyState !== EventSource.OPEN) return
        if (Date.now() - lastEventAt > STALE_THRESHOLD_MS) {
          eventSource.close()
        }
      }, 5000)
    }

    function stopStaleCheck() {
      if (staleCheckInterval) {
        clearInterval(staleCheckInterval)
        staleCheckInterval = null
      }
    }

    const eventTypes = [
      'incident_created',
      'state_changed',
      'evidence_added',
      'recommendation_ready',
      'execution_started',
      'execution_log',
      'execution_completed',
      'verification_result',
      'investigation_progress',
    ]

    eventTypes.forEach((type) => {
      eventSource.addEventListener(type, (event) => {
        markActivity()
        try {
          const data = JSON.parse(event.data)
          handlers[type]?.(data)
        } catch {
          // Ignore parse errors
        }
      })
    })

    eventSource.addEventListener('heartbeat', markActivity)
  }

  onConnectionChange?.({ connected: false, retrying: false, initial: true })
  connect()

  return {
    close() {
      closed = true
      if (staleCheckInterval) clearInterval(staleCheckInterval)
      eventSource?.close()
      onConnectionChange?.({ connected: false, retrying: false, initial: false })
    },
  }
}
