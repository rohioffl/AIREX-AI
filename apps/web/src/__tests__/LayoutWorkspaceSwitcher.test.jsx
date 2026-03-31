import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockToggle = vi.hoisted(() => vi.fn())
const mockLogout = vi.hoisted(() => vi.fn())
const mockSwitchTenant = vi.hoisted(() => vi.fn())

const mockAuth = vi.hoisted(() => ({
  user: { role: 'operator', email: 'ava@example.com', displayName: 'Ava Admin', userId: 'user-1' },
  logout: mockLogout,
  tenants: [
    { id: 'tenant-1', name: 'alpha', display_name: 'Alpha', organization_id: 'org-1', cloud: 'aws' },
    { id: 'tenant-2', name: 'beta', display_name: 'Beta', organization_id: 'org-1', cloud: 'gcp' },
  ],
  activeTenant: { id: 'tenant-1', name: 'alpha', display_name: 'Alpha' },
  activeOrganization: { id: 'org-1', name: 'Acme Cloud', slug: 'acme-cloud' },
  switchTenant: mockSwitchTenant,
  organizations: [{ id: 'org-1', name: 'Acme Cloud', slug: 'acme-cloud' }],
  organizationMemberships: [{ id: 'org-1', role: 'admin' }],
  tenantMemberships: [{ id: 'tenant-1', role: 'admin' }],
}))

vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({ isDark: true, toggle: mockToggle }),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockAuth,
}))

vi.mock('../services/sse', () => ({
  createSSEConnection: () => ({ close: () => {} }),
}))

vi.mock('../components/common/ToastContainer', () => ({
  default: () => null,
}))

vi.mock('../components/layout/LeadApprovalPanel', () => ({
  default: () => null,
}))

const mockApi = vi.hoisted(() => ({
  fetchIncidents: vi.fn(),
  fetchUserAccessibleTenants: vi.fn(),
}))

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    fetchIncidents: mockApi.fetchIncidents,
    fetchUserAccessibleTenants: mockApi.fetchUserAccessibleTenants,
  }
})

import Layout from '../components/layout/Layout'

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>
}

describe('Layout workspace switcher', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    mockAuth.user = { role: 'operator', email: 'ava@example.com', displayName: 'Ava Admin', userId: 'user-1' }
    mockAuth.activeOrganization = { id: 'org-1', name: 'Acme Cloud', slug: 'acme-cloud' }
    mockAuth.organizations = [
      { id: 'org-1', name: 'Acme Cloud', slug: 'acme-cloud' },
      { id: 'org-2', name: 'Dormant Org', slug: 'dormant-org' },
    ]
    mockAuth.tenantMemberships = [{ id: 'tenant-1', role: 'admin' }]
    mockApi.fetchIncidents.mockResolvedValue({ items: [] })
    mockApi.fetchUserAccessibleTenants.mockResolvedValue([
      {
        id: 'tenant-1',
        name: 'alpha',
        display_name: 'Alpha',
        cloud: 'aws',
        organization_id: 'org-1',
        role: 'admin',
      },
      {
        id: 'tenant-2',
        name: 'beta',
        display_name: 'Beta',
        cloud: 'gcp',
        organization_id: 'org-1',
        role: null,
      },
    ])
  })

  it('loads accessible tenants and switches from the sidebar', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
          <LocationProbe />
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    await user.click(screen.getByRole('button', { name: /alpha/i }))
    expect(await screen.findByText('Switch Workspace')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('inherited')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /beta/i }))
    await waitFor(() => {
      expect(mockSwitchTenant).toHaveBeenCalledWith('tenant-2')
    })
  })

  it('keeps all workspaces selected when navigating from workspaces to alerts', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/admin/workspaces']}>
        <Layout>
          <div>content</div>
          <LocationProbe />
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    await user.click(screen.getByRole('button', { name: /alpha/i }))
    await user.click(await screen.findByRole('button', { name: /all workspaces/i }))
    expect(screen.getByTestId('location')).toHaveTextContent('/admin/workspaces')
    await user.click(screen.getByRole('link', { name: /alerts/i }))
    expect(screen.getByRole('button', { name: /all workspaces/i })).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/alerts')
    expect(mockSwitchTenant).not.toHaveBeenCalled()
  })

  it('keeps users on alerts when switching to all workspaces', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/alerts']}>
        <Layout>
          <div>content</div>
          <LocationProbe />
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    await user.click(screen.getByRole('button', { name: /alpha/i }))
    await user.click(await screen.findByRole('button', { name: /all workspaces/i }))

    expect(screen.getByTestId('location')).toHaveTextContent('/alerts')
    expect(screen.getAllByRole('button', { name: /all workspaces/i }).length).toBeGreaterThan(0)
  })

  it('keeps users on alerts when switching tenants', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/alerts']}>
        <Layout>
          <div>content</div>
          <LocationProbe />
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    await user.click(screen.getByRole('button', { name: /alpha/i }))
    await user.click(screen.getByRole('button', { name: /beta/i }))

    await waitFor(() => {
      expect(mockSwitchTenant).toHaveBeenCalledWith('tenant-2')
    })
    expect(screen.getByTestId('location')).toHaveTextContent('/alerts')
  })

  it('hides all tenants option for tenant-scoped users', async () => {
    const user = userEvent.setup()
    mockAuth.activeOrganization = {
      id: 'org-1',
      name: 'Acme Cloud',
      slug: 'acme-cloud',
      role: 'tenant_member',
    }

    render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
          <LocationProbe />
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    await user.click(screen.getByRole('button', { name: /alpha/i }))

    expect(await screen.findByText('Switch Workspace')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /all tenants/i })).not.toBeInTheDocument()
  })

  it('shows organizations with no workspaces in the org switcher', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
          <LocationProbe />
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    await user.click(screen.getByRole('button', { name: /acme cloud/i }))

    expect(await screen.findByText('Dormant Org')).toBeInTheDocument()
    expect(screen.getByText('No workspaces')).toBeInTheDocument()
  })

  it('lets users switch to an organization with no workspaces for onboarding', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
          <LocationProbe />
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    await user.click(screen.getByRole('button', { name: /acme cloud/i }))
    await user.click(await screen.findByRole('button', { name: /dormant org/i }))

    expect(screen.getAllByRole('button', { name: /dormant org/i }).length).toBeGreaterThan(0)
    expect(
      screen.getByRole('button', { name: /no workspaceworkspace scope/i })
    ).toBeInTheDocument()
  })

  it('keeps the selected organization visible while switching to a workspace in another org', async () => {
    const user = userEvent.setup()
    mockApi.fetchUserAccessibleTenants.mockResolvedValue([
      {
        id: 'tenant-1',
        name: 'alpha',
        display_name: 'Alpha',
        cloud: 'aws',
        organization_id: 'org-1',
        role: 'admin',
      },
      {
        id: 'tenant-3',
        name: 'gamma',
        display_name: 'Gamma',
        cloud: 'aws',
        organization_id: 'org-2',
        role: 'admin',
      },
    ])

    render(
      <MemoryRouter initialEntries={['/alerts']}>
        <Layout>
          <div>content</div>
          <LocationProbe />
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    await user.click(screen.getByRole('button', { name: /acme cloud/i }))
    await user.click(await screen.findByRole('button', { name: /dormant org/i }))

    await waitFor(() => {
      expect(mockSwitchTenant).toHaveBeenCalledWith('tenant-3')
    })

    expect(screen.getAllByRole('button', { name: /dormant org/i }).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /select workspaceworkspace scope/i })).toBeInTheDocument()
  })

  it('syncs the organization switcher from the org slug route', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/organizations/dormant-org']}>
        <Layout>
          <div>content</div>
          <LocationProbe />
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    expect(screen.getByRole('button', { name: /dormant org/i })).toBeInTheDocument()
  })

  it('clears a stale org override that does not belong to the current user session', async () => {
    window.localStorage.setItem('airex-active-organization-id', 'org-2')
    mockAuth.organizations = [{ id: 'org-1', name: 'Acme Cloud', slug: 'acme-cloud' }]
    mockAuth.activeOrganization = { id: 'org-1', name: 'Acme Cloud', slug: 'acme-cloud' }

    render(
      <MemoryRouter initialEntries={['/alerts']}>
        <Layout>
          <div>content</div>
          <LocationProbe />
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    expect(screen.getByRole('button', { name: /alpha.*workspace scope/i })).toBeInTheDocument()
    expect(window.localStorage.getItem('airex-active-organization-id')).toBeNull()
  })

  it('shows tenant admin surfaces when admin access comes from organization membership', async () => {
    mockAuth.user = {
      role: 'viewer',
      email: 'rohit@example.com',
      displayName: 'Rohit',
      userId: 'user-1',
    }
    mockAuth.activeOrganization = { id: 'org-1', name: 'Acme Cloud', slug: 'acme-cloud', role: 'admin' }
    mockAuth.organizationMemberships = [{ id: 'org-1', role: 'admin' }]
    mockAuth.tenantMemberships = []

    render(
      <MemoryRouter initialEntries={['/alerts']}>
        <Layout>
          <div>content</div>
          <LocationProbe />
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    expect(screen.getByRole('link', { name: /runbooks/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /reports/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^settings$/i })).toBeInTheDocument()
  })
})
