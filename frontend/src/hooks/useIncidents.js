import { useState, useEffect, useCallback } from 'react'
import { fetchIncidents } from '../services/api'
import { createSSEConnection } from '../services/sse'

const TENANT_ID = localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000000'

export default function useIncidents() {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [filters, setFilters] = useState({ state: null, severity: null, alertType: null })
  const [nextCursor, setNextCursor] = useState(null)
  const [hasMore, setHasMore] = useState(false)
  const [total, setTotal] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchIncidents(filters)
      setIncidents(data.items || data)
      setNextCursor(data.next_cursor || null)
      setHasMore(data.has_more || false)
      if (data.total != null) setTotal(data.total)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [filters])

  const loadMore = useCallback(async () => {
    if (!nextCursor || !hasMore) return
    try {
      const data = await fetchIncidents({ ...filters, cursor: nextCursor })
      setIncidents(prev => [...prev, ...(data.items || data)])
      setNextCursor(data.next_cursor || null)
      setHasMore(data.has_more || false)
    } catch (err) {
      setError(err.message)
    }
  }, [filters, nextCursor, hasMore])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const sse = createSSEConnection(
      TENANT_ID,
      {
        incident_created(data) {
          setIncidents((prev) => [data, ...prev])
        },
        state_changed(data) {
          setIncidents((prev) =>
            prev.map((inc) =>
              inc.id === data.incident_id ? { ...inc, state: data.new_state } : inc
            )
          )
        },
      },
      (status) => {
        setConnected(status.connected)
        setReconnecting(status.retrying)
      }
    )

    return () => sse.close()
  }, [])

  return { incidents, loading, error, connected, reconnecting, filters, setFilters, reload: load, loadMore, hasMore, total }
}
