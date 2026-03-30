import { useState, useEffect, useCallback } from 'react'
import { fetchIncidents } from '../services/api'
import { createSSEConnection } from '../services/sse'

export default function useIncidents(initialFilters = {}) {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [filters, setFilters] = useState({
    state: null,
    severity: null,
    alertType: null,
    search: null,
    host_key: null,
    organizationId: null,
    ...initialFilters,
  })
  const [nextCursor, setNextCursor] = useState(null)
  const [hasMore, setHasMore] = useState(false)
  const [total, setTotal] = useState(null)

  const load = useCallback(async (opts = {}) => {
    const silent = Boolean(opts.silent)
    if (!silent) setLoading(true)
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
      if (!silent) setLoading(false)
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
    setFilters((prev) => {
      if (prev.organizationId === (initialFilters.organizationId || null)) {
        return prev
      }
      return {
        ...prev,
        organizationId: initialFilters.organizationId || null,
      }
    })
  }, [initialFilters.organizationId])

  // Background refresh so repeated alerts (meta/updated_at changes) show up.
  useEffect(() => {
    const interval = setInterval(() => {
      load({ silent: true })
    }, 60000)
    return () => clearInterval(interval)
  }, [load])

  useEffect(() => {
    const sse = createSSEConnection(
      {
        incident_created(data) {
          const normalized = data.id ? data : { ...data, id: data.incident_id }
          setIncidents((prev) => {
            const withoutDupes = prev.filter((inc) => (inc.id || inc.incident_id) !== normalized.id)
            return [normalized, ...withoutDupes]
          })
          load({ silent: true })
        },
        state_changed(data) {
          setIncidents((prev) =>
            prev.map((inc) => {
              const incidentId = inc.id || inc.incident_id
              return incidentId === data.incident_id ? { ...inc, state: data.new_state } : inc
            })
          )
          load({ silent: true })
        },
      },
      (status) => {
        setConnected(status.connected)
        setReconnecting(status.retrying)
      }
    )

    return () => sse.close()
  }, [load])

  return { incidents, loading, error, connected, reconnecting, filters, setFilters, reload: load, loadMore, hasMore, total }
}
