import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockApi = vi.hoisted(() => ({
  fetchOrganizations: vi.fn(),
  fetchOrganizationTenants: vi.fn(),
  fetchTenants: vi.fn(),
  fetchProjects: vi.fn(),
  fetchIntegrations: vi.fn(),
}))

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    fetchOrganizations: mockApi.fetchOrganizations,
    fetchOrganizationTenants: mockApi.fetchOrganizationTenants,
    fetchTenants: mockApi.fetchTenants,
    fetchProjects: mockApi.fetchProjects,
    fetchIntegrations: mockApi.fetchIntegrations,
  }
})

import { useTenantWorkspace } from '../hooks/useTenantWorkspace'

describe('useTenantWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.fetchOrganizations.mockResolvedValue([
      { id: 'org-1', name: 'Ankercloud', slug: 'ankercloud', status: 'active' },
    ])
    mockApi.fetchOrganizationTenants.mockResolvedValue([
      {
        id: 'tenant-1',
        name: 'uno-secur',
        display_name: 'UnoSecur',
        cloud: 'aws',
      },
    ])
    mockApi.fetchTenants.mockResolvedValue([])
    mockApi.fetchProjects.mockResolvedValue([
      { id: 'project-1', tenant_id: 'tenant-1', name: 'Project-1', slug: 'project-1' },
    ])
    mockApi.fetchIntegrations.mockResolvedValue([
      { id: 'integration-1', tenant_id: 'tenant-1', name: 'Primary Site24x7', slug: 'primary-site24x7' },
    ])
  })

  it('bootstraps organizations, tenants, projects, and integrations for the active tenant', async () => {
    const onError = vi.fn()
    const { result } = renderHook(() => useTenantWorkspace({ onError }))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
      expect(result.current.selectedTenant?.display_name).toBe('UnoSecur')
      expect(result.current.projects).toHaveLength(1)
      expect(result.current.integrations).toHaveLength(1)
    })

    expect(onError).not.toHaveBeenCalled()
    expect(mockApi.fetchOrganizations).toHaveBeenCalledTimes(1)
    expect(mockApi.fetchOrganizationTenants).toHaveBeenCalledWith('org-1')
    expect(mockApi.fetchProjects).toHaveBeenCalledWith('tenant-1')
    expect(mockApi.fetchIntegrations).toHaveBeenCalledWith('tenant-1')
  })

  it('does not refetch the workspace when the onError callback identity changes', async () => {
    const initialOnError = vi.fn()
    const { rerender } = renderHook(
      ({ onError }) => useTenantWorkspace({ onError }),
      { initialProps: { onError: initialOnError } }
    )

    await waitFor(() => {
      expect(mockApi.fetchOrganizations).toHaveBeenCalledTimes(1)
      expect(mockApi.fetchOrganizationTenants).toHaveBeenCalledTimes(1)
      expect(mockApi.fetchProjects).toHaveBeenCalledTimes(1)
      expect(mockApi.fetchIntegrations).toHaveBeenCalledTimes(1)
    })

    rerender({ onError: vi.fn() })

    await waitFor(() => {
      expect(mockApi.fetchOrganizations).toHaveBeenCalledTimes(1)
      expect(mockApi.fetchOrganizationTenants).toHaveBeenCalledTimes(1)
      expect(mockApi.fetchProjects).toHaveBeenCalledTimes(1)
      expect(mockApi.fetchIntegrations).toHaveBeenCalledTimes(1)
    })
  })
})
