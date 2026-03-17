import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockAddToast = vi.hoisted(() => vi.fn())

vi.mock('../context/ToastContext', () => ({
  useToasts: () => ({ addToast: mockAddToast }),
}))

const mockWorkspace = vi.hoisted(() => ({
  organizations: [{ id: 'org-1', name: 'Ankercloud' }],
  activeOrganizationId: 'org-1',
  tenants: [
    {
      id: 'tenant-1',
      name: 'uno-secur',
      display_name: 'UnoSecur',
      cloud: 'aws',
      organization_name: 'Ankercloud',
      credential_status: 'configured',
      server_count: 3,
    },
  ],
  selectedTenantId: 'tenant-1',
  selectedTenant: {
    id: 'tenant-1',
    name: 'uno-secur',
    display_name: 'UnoSecur',
    cloud: 'aws',
  },
  projects: [
    { id: 'project-1', name: 'Project-1', slug: 'project-1', description: 'Core API', is_active: true },
  ],
  integrations: [
    { id: 'integration-1', name: 'Primary Site24x7', slug: 'primary-site24x7', integration_type_key: 'site24x7', enabled: true, status: 'configured' },
  ],
  loading: false,
  detailLoading: false,
  setSelectedTenantId: vi.fn(),
  changeOrganization: vi.fn(),
  loadWorkspace: vi.fn(),
  reloadWorkspace: vi.fn(),
}))

vi.mock('../hooks/useTenantWorkspace', () => ({
  useTenantWorkspace: () => mockWorkspace,
}))

const mockApi = vi.hoisted(() => ({
  reloadTenants: vi.fn(),
  fetchTenantDetail: vi.fn(),
  deleteTenant: vi.fn(),
  deleteProject: vi.fn(),
  testIntegration: vi.fn(),
  syncIntegrationMonitors: vi.fn(),
  fetchExternalMonitors: vi.fn(),
  fetchProjectMonitorBindings: vi.fn(),
  createProjectMonitorBinding: vi.fn(),
  deleteProjectMonitorBinding: vi.fn(),
  deleteIntegration: vi.fn(),
  createOrganization: vi.fn(),
  createOrganizationTenant: vi.fn(),
  createProject: vi.fn(),
  createIntegration: vi.fn(),
  fetchIntegrationTypes: vi.fn(),
}))

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    reloadTenants: mockApi.reloadTenants,
    fetchTenantDetail: mockApi.fetchTenantDetail,
    deleteTenant: mockApi.deleteTenant,
    deleteProject: mockApi.deleteProject,
    testIntegration: mockApi.testIntegration,
    syncIntegrationMonitors: mockApi.syncIntegrationMonitors,
    fetchExternalMonitors: mockApi.fetchExternalMonitors,
    fetchProjectMonitorBindings: mockApi.fetchProjectMonitorBindings,
    createProjectMonitorBinding: mockApi.createProjectMonitorBinding,
    deleteProjectMonitorBinding: mockApi.deleteProjectMonitorBinding,
    deleteIntegration: mockApi.deleteIntegration,
    createOrganization: mockApi.createOrganization,
    createOrganizationTenant: mockApi.createOrganizationTenant,
    createProject: mockApi.createProject,
    createIntegration: mockApi.createIntegration,
    fetchIntegrationTypes: mockApi.fetchIntegrationTypes,
  }
})

import TenantWorkspaceManager from '../components/admin/TenantWorkspaceManager'

describe('TenantWorkspaceManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAddToast.mockReset()
    mockApi.testIntegration.mockResolvedValue({ status: 'verified' })
    mockApi.syncIntegrationMonitors.mockResolvedValue({ status: 'synced', monitor_count: 0 })
    mockApi.fetchProjectMonitorBindings.mockResolvedValue([])
    mockApi.fetchExternalMonitors.mockResolvedValue([
      {
        id: 'external-monitor-1',
        external_monitor_id: 'site24x7:1001',
        external_name: 'CPU Critical',
        monitor_type: 'cpu',
        status: 'synced',
        enabled: true,
      },
    ])
    mockApi.createProjectMonitorBinding.mockResolvedValue({ id: 'binding-1' })
    mockApi.deleteProjectMonitorBinding.mockResolvedValue({ status: 'deleted' })
  })

  it('renders the selected tenant workspace', async () => {
    render(<TenantWorkspaceManager />)

    expect(screen.getByText('UnoSecur')).toBeInTheDocument()
    expect(screen.getByText('Projects · UnoSecur')).toBeInTheDocument()
    expect(screen.getByText('Project-1')).toBeInTheDocument()
    expect(screen.getByText('Primary Site24x7')).toBeInTheDocument()

    await waitFor(() => {
      expect(mockApi.fetchProjectMonitorBindings).toHaveBeenCalledWith('project-1')
    })
  })

  it('runs integration verify and sync actions', async () => {
    const user = userEvent.setup()
    render(<TenantWorkspaceManager />)

    await user.click(screen.getByRole('button', { name: /verify/i }))
    await user.click(screen.getByRole('button', { name: /sync monitors/i }))

    await waitFor(() => {
      expect(mockApi.testIntegration).toHaveBeenCalledWith('integration-1')
      expect(mockApi.syncIntegrationMonitors).toHaveBeenCalledWith('integration-1', [])
      expect(mockWorkspace.loadWorkspace).toHaveBeenCalledWith('tenant-1')
    })
  })

  it('loads external monitors and binds a monitor to a project', async () => {
    const user = userEvent.setup()
    render(<TenantWorkspaceManager mode="integrations" />)

    await user.click(screen.getByRole('button', { name: /load external monitors/i }))

    expect(await screen.findByText('CPU Critical')).toBeInTheDocument()
    await user.selectOptions(screen.getByRole('combobox', { name: /bind cpu critical to project/i }), 'project-1')
    await user.click(screen.getByRole('button', { name: /bind to project/i }))

    await waitFor(() => {
      expect(mockApi.fetchExternalMonitors).toHaveBeenCalledWith('integration-1')
      expect(mockApi.createProjectMonitorBinding).toHaveBeenCalledWith('project-1', {
        external_monitor_id: 'external-monitor-1',
        enabled: true,
      })
    })
  })
})
