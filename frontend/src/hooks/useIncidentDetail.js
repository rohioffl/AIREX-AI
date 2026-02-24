import { useState, useEffect, useCallback, useRef } from 'react'
import { fetchIncident } from '../services/api'
import { createSSEConnection } from '../services/sse'

export default function useIncidentDetail(id) {
  const [incident, setIncident] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [executionLogs, setExecutionLogs] = useState([])
  const sseRef = useRef(null)

  const load = useCallback(async (opts = {}) => {
    const silent = Boolean(opts.silent)
    if (!silent) setLoading(true)
    setError(null)
    try {
      const data = await fetchIncident(id)
      setIncident(data)
    } catch (err) {
      setError(err.message)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  // Background refresh so repeated alerts update meta without UI flicker.
  useEffect(() => {
    if (!id) return
    const interval = setInterval(() => {
      load({ silent: true })
    }, 30000)
    return () => clearInterval(interval)
  }, [id, load])

  useEffect(() => {
    const sse = createSSEConnection(
      {
        state_changed(data) {
          if (data.incident_id === id) {
            setIncident((prev) => prev ? { ...prev, state: data.new_state } : prev)
            load({ silent: true })
          }
        },
        evidence_added(data) {
          if (data.incident_id === id) {
            setIncident((prev) =>
              prev ? { ...prev, evidence: [...(prev.evidence || []), data] } : prev
            )
          }
        },
        recommendation_ready(data) {
          if (data.incident_id === id) {
            load()
          }
        },
        execution_started(data) {
          if (data.incident_id === id) {
            setIncident((prev) => prev ? { ...prev, state: 'EXECUTING' } : prev)
          }
        },
        execution_log(data) {
          if (data.incident_id === id) {
            setExecutionLogs((prev) => [...prev, data.line])
          }
        },
        execution_completed(data) {
          if (data.incident_id === id) {
            load()
          }
        },
        verification_result(data) {
          if (data.incident_id === id) {
            load()
          }
        },
      },
      (status) => {
        setConnected(status.connected)
        setReconnecting(status.retrying)
      }
    )
    sseRef.current = sse

    return () => sse.close()
  }, [id, load])

  return { incident, loading, error, connected, reconnecting, executionLogs, reload: load }
}
