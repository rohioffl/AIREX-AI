import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockAuth = vi.hoisted(() => ({
  user: { role: 'platform_admin' },
  activeTenantId: 'tenant-1',
  projects: [],
  organizations: [],
  tenants: [],
  organizationMemberships: [],
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockAuth,
}))

vi.mock('../services/api', () => ({
  fetchIntegrationTypes: vi.fn(async () => []),
  fetchIntegrations: vi.fn(async () => []),
  fetchProjects: vi.fn(async () => []),
  deleteIntegration: vi.fn(async () => ({})),
  testIntegration: vi.fn(async () => ({})),
  syncIntegrationMonitors: vi.fn(async () => ({})),
  fetchWebhookEvents: vi.fn(async () => []),
  replayWebhookEvent: vi.fn(async () => ({})),
  rotateIntegrationSecret: vi.fn(async () => ({})),
}))

vi.mock('../components/admin/TenantWorkspaceManager', () => ({
  default: ({ mode }) => <div data-testid="tenant-workspace-manager">{mode}</div>,
}))

import OrganizationsAdminPage from '../pages/admin/OrganizationsAdminPage'
import TenantWorkspaceAdminPage from '../pages/admin/TenantWorkspaceAdminPage'
import IntegrationsAdminPage from '../pages/admin/IntegrationsAdminPage'

describe('admin workspace route pages', () => {
  beforeEach(() => {
    mockAuth.user = { role: 'platform_admin' }
    mockAuth.activeTenantId = 'tenant-1'
    mockAuth.projects = []
    mockAuth.organizations = []
    mockAuth.tenants = []
    mockAuth.organizationMemberships = []
  })

  it('renders the organizations admin page wrapper', () => {
    render(
      <MemoryRouter>
        <OrganizationsAdminPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Organization Admin')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to platform admin/i })).toBeInTheDocument()
    expect(screen.getByTestId('tenant-workspace-manager')).toHaveTextContent('organizations')
  })

  it('renders the tenant workspace admin page wrapper', () => {
    render(
      <MemoryRouter>
        <TenantWorkspaceAdminPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Tenant Workspaces')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to platform admin/i })).toBeInTheDocument()
    expect(screen.getByTestId('tenant-workspace-manager')).toHaveTextContent('workspace')
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
      <MemoryRouter>
        <OrganizationsAdminPage />
      </MemoryRouter>
    )

    expect(screen.getByRole('link', { name: /back to dashboard/i })).toBeInTheDocument()
    organizationsView.unmount()

    const workspacesView = render(
      <MemoryRouter>
        <TenantWorkspaceAdminPage />
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
