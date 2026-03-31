import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockAuth = vi.hoisted(() => ({
  user: { role: 'platform_admin' },
  activeTenantId: 'tenant-1',
  activeTenant: { id: 'tenant-1', display_name: 'Tenant One', name: 'tenant-one' },
  activeOrganization: { id: 'org-1', name: 'Org One' },
  projects: [],
  organizations: [{ id: 'org-1', name: 'Org One' }],
  tenants: [{ id: 'tenant-1', display_name: 'Tenant One', name: 'tenant-one' }],
  organizationMemberships: [],
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockAuth,
}))

const mockApi = vi.hoisted(() => ({
  fetchIntegrationTypes: vi.fn(async () => []),
  fetchIntegrations: vi.fn(async () => []),
  fetchOrganizations: vi.fn(async () => [{ id: 'org-1', name: 'Org One', slug: 'org-one' }]),
  fetchOrganizationTenants: vi.fn(async () => [{ id: 'tenant-1', display_name: 'Tenant One', name: 'tenant-one', organization_id: 'org-1' }]),
  fetchProjects: vi.fn(async () => []),
  deleteIntegration: vi.fn(async () => ({})),
  testIntegration: vi.fn(async () => ({})),
  syncIntegrationMonitors: vi.fn(async () => ({})),
  fetchWebhookEvents: vi.fn(async () => []),
  replayWebhookEvent: vi.fn(async () => ({})),
  rotateIntegrationSecret: vi.fn(async () => ({})),
}))

vi.mock('../services/api', () => ({
  fetchIntegrationTypes: mockApi.fetchIntegrationTypes,
  fetchIntegrations: mockApi.fetchIntegrations,
  fetchOrganizations: mockApi.fetchOrganizations,
  fetchOrganizationTenants: mockApi.fetchOrganizationTenants,
  fetchProjects: mockApi.fetchProjects,
  deleteIntegration: mockApi.deleteIntegration,
  testIntegration: mockApi.testIntegration,
  syncIntegrationMonitors: mockApi.syncIntegrationMonitors,
  fetchWebhookEvents: mockApi.fetchWebhookEvents,
  replayWebhookEvent: mockApi.replayWebhookEvent,
  rotateIntegrationSecret: mockApi.rotateIntegrationSecret,
}))

vi.mock('../components/admin/TenantWorkspaceManager', () => ({
  default: ({ mode, initialOrganizationId }) => (
    <div data-testid="tenant-workspace-manager">
      {mode}:{initialOrganizationId || 'none'}
    </div>
  ),
}))

vi.mock('../components/admin/AccessMatrixView', () => ({
  default: ({ organization, tenants }) => (
    <div data-testid="access-matrix-view">
      {organization?.name}|{Array.isArray(tenants) ? tenants.length : 0}
    </div>
  ),
}))

vi.mock('../components/admin/TenantAccessDrawer', () => ({
  default: () => null,
}))

vi.mock('../components/admin/TenantMembersPanel', () => ({
  default: ({ tenant }) => <div data-testid="tenant-members-panel">{tenant?.display_name || tenant?.name}</div>,
}))

import OrganizationsAdminPage from '../pages/admin/OrganizationsAdminPage'
import TenantWorkspaceAdminPage from '../pages/admin/TenantWorkspaceAdminPage'
import IntegrationsAdminPage from '../pages/admin/IntegrationsAdminPage'

describe('admin workspace route pages', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    mockAuth.user = { role: 'platform_admin' }
    mockAuth.activeTenantId = 'tenant-1'
    mockAuth.activeTenant = { id: 'tenant-1', display_name: 'Tenant One', name: 'tenant-one' }
    mockAuth.activeOrganization = { id: 'org-1', name: 'Org One', slug: 'org-one' }
    mockAuth.projects = []
    mockAuth.organizations = [
      { id: 'org-1', name: 'Org One', slug: 'org-one' },
      { id: 'org-2', name: 'Org Two', slug: 'org-two' },
    ]
    mockAuth.tenants = [{ id: 'tenant-1', display_name: 'Tenant One', name: 'tenant-one' }]
    mockAuth.organizationMemberships = []
    mockApi.fetchOrganizations.mockResolvedValue([
      { id: 'org-1', name: 'Org One', slug: 'org-one' },
      { id: 'org-2', name: 'Org Two', slug: 'org-two' },
    ])
    mockApi.fetchOrganizationTenants.mockImplementation(async (organizationId) => (
      organizationId === 'org-2'
        ? []
        : [{ id: 'tenant-1', display_name: 'Tenant One', name: 'tenant-one', organization_id: 'org-1' }]
    ))
  })

  it('renders the organizations admin page wrapper', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/organizations/org-one']}>
        <Routes>
          <Route path="/admin/organizations/:organizationSlug" element={<OrganizationsAdminPage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Organization Admin')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to platform admin/i })).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByTestId('access-matrix-view')).toHaveTextContent('Org One|1')
      expect(screen.getByTestId('tenant-workspace-manager')).toHaveTextContent('organizations:org-1')
    })
  })

  it('pins org admin to the requested organization instead of falling back to the active org', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/organizations/org-two']}>
        <Routes>
          <Route path="/admin/organizations/:organizationSlug" element={<OrganizationsAdminPage />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByTestId('access-matrix-view')).toHaveTextContent('Org Two|0')
      expect(screen.getByTestId('tenant-workspace-manager')).toHaveTextContent('organizations:org-2')
    })
  })

  it('renders the workspace admin page wrapper', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/organizations/org-one/workspaces']}>
        <Routes>
          <Route path="/admin/organizations/:organizationSlug/workspaces" element={<TenantWorkspaceAdminPage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Workspaces')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to platform admin/i })).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByTestId('tenant-members-panel')).toHaveTextContent('Tenant One')
    })
  })

  it('scopes the workspace page to the requested organization', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/organizations/org-two/workspaces']}>
        <Routes>
          <Route path="/admin/organizations/:organizationSlug/workspaces" element={<TenantWorkspaceAdminPage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Workspaces')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('Workspaces (0)')).toBeInTheDocument()
      expect(screen.getByText('No workspaces found')).toBeInTheDocument()
    })
  })

  it('renders the integrations admin page wrapper', async () => {
    render(
      <MemoryRouter>
        <IntegrationsAdminPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Monitoring Integrations')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to platform admin/i })).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.queryByText('Monitoring Integrations')).toBeInTheDocument()
    })
  })

  it('uses org-scoped back links for non-platform admins', async () => {
    mockAuth.user = { role: 'org_admin' }
    mockAuth.organizationMemberships = [{ id: 'org-1', role: 'org_admin' }]

    const organizationsView = render(
      <MemoryRouter initialEntries={['/admin/organizations/org-one']}>
        <Routes>
          <Route path="/admin/organizations/:organizationSlug" element={<OrganizationsAdminPage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByRole('link', { name: /back to dashboard/i })).toBeInTheDocument()
    organizationsView.unmount()

    const workspacesView = render(
      <MemoryRouter initialEntries={['/admin/organizations/org-one/workspaces']}>
        <Routes>
          <Route path="/admin/organizations/:organizationSlug/workspaces" element={<TenantWorkspaceAdminPage />} />
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByRole('link', { name: /back to organizations/i })).toBeInTheDocument()
    workspacesView.unmount()

    render(
      <MemoryRouter>
        <IntegrationsAdminPage />
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByRole('link', { name: /back to workspaces/i })).toBeInTheDocument()
    })
  })
})
