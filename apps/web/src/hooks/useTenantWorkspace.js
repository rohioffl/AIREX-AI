import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  fetchIntegrations,
  fetchOrganizationTenants,
  fetchOrganizations,
  fetchProjects,
  fetchTenants,
} from '../services/api'

export function useTenantWorkspace({ onError, loadDetails = true, initialOrganizationId = null }) {
  const onErrorRef = useRef(onError)
  const [organizations, setOrganizations] = useState([])
  const [activeOrganizationId, setActiveOrganizationId] = useState(null)
  const [tenants, setTenants] = useState([])
  const [selectedTenantId, setSelectedTenantId] = useState(null)
  const [projects, setProjects] = useState([])
  const [integrations, setIntegrations] = useState([])
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  const reportError = useCallback((message) => {
    onErrorRef.current?.(message)
  }, [])

  const loadTenants = useCallback(async (organizationId, preferredTenantId = null) => {
    const data = organizationId
      ? await fetchOrganizationTenants(organizationId)
      : await fetchTenants()
    const nextTenants = Array.isArray(data) ? data : []
    setTenants(nextTenants)
    const nextSelectedTenantId = nextTenants.some((tenant) => tenant.id === preferredTenantId)
      ? preferredTenantId
      : (nextTenants[0]?.id || null)
    setSelectedTenantId(nextSelectedTenantId)
    return nextTenants
  }, [])

  const loadWorkspace = useCallback(async (tenantId) => {
    if (!loadDetails) {
      setProjects([])
      setIntegrations([])
      setDetailLoading(false)
      return
    }
    if (!tenantId) {
      setProjects([])
      setIntegrations([])
      return
    }

    setDetailLoading(true)
    try {
      const [projectData, integrationData] = await Promise.all([
        fetchProjects(tenantId),
        fetchIntegrations(tenantId),
      ])
      setProjects(Array.isArray(projectData) ? projectData : [])
      setIntegrations(Array.isArray(integrationData) ? integrationData : [])
    } catch {
      reportError('Failed to load tenant workspace')
    } finally {
      setDetailLoading(false)
    }
  }, [loadDetails, reportError])

  const bootstrapWorkspace = useCallback(async () => {
    try {
      setLoading(true)
      const orgData = await fetchOrganizations().catch(() => [])
      const nextOrganizations = Array.isArray(orgData) ? orgData : []
      setOrganizations(nextOrganizations)
      const nextOrganizationId = nextOrganizations.some((org) => org.id === initialOrganizationId)
        ? initialOrganizationId
        : (nextOrganizations[0]?.id || null)
      setActiveOrganizationId(nextOrganizationId)
      await loadTenants(nextOrganizationId, null)
    } catch {
      reportError('Failed to load tenants')
    } finally {
      setLoading(false)
    }
  }, [initialOrganizationId, loadTenants, reportError])

  const reloadWorkspace = useCallback(async () => {
    try {
      setLoading(true)
      const orgData = await fetchOrganizations().catch(() => [])
      const nextOrganizations = Array.isArray(orgData) ? orgData : []
      setOrganizations(nextOrganizations)
      const nextOrganizationId = nextOrganizations.some((org) => org.id === activeOrganizationId)
        ? activeOrganizationId
        : (nextOrganizations[0]?.id || null)
      setActiveOrganizationId(nextOrganizationId)
      await loadTenants(nextOrganizationId, selectedTenantId)
    } catch {
      reportError('Failed to load tenants')
    } finally {
      setLoading(false)
    }
  }, [activeOrganizationId, loadTenants, reportError, selectedTenantId])

  const changeOrganization = useCallback(async (organizationId) => {
    setActiveOrganizationId(organizationId)
    try {
      setLoading(true)
      await loadTenants(organizationId, null)
    } catch {
      reportError('Failed to switch organization')
    } finally {
      setLoading(false)
    }
  }, [loadTenants, reportError])

  useEffect(() => {
    bootstrapWorkspace()
  }, [bootstrapWorkspace])

  useEffect(() => {
    if (!initialOrganizationId) return
    if (initialOrganizationId === activeOrganizationId) return
    if (organizations.length > 0 && !organizations.some((org) => org.id === initialOrganizationId)) return
    changeOrganization(initialOrganizationId)
  }, [activeOrganizationId, changeOrganization, initialOrganizationId, organizations])

  useEffect(() => {
    if (!loadDetails) {
      return
    }
    loadWorkspace(selectedTenantId)
  }, [loadDetails, loadWorkspace, selectedTenantId])

  const selectedTenant = useMemo(
    () => tenants.find((tenant) => tenant.id === selectedTenantId) || null,
    [selectedTenantId, tenants]
  )

  return {
    organizations,
    activeOrganizationId,
    tenants,
    selectedTenantId,
    selectedTenant,
    projects,
    integrations,
    loading,
    detailLoading,
    setSelectedTenantId,
    changeOrganization,
    loadWorkspace,
    reloadWorkspace,
  }
}
