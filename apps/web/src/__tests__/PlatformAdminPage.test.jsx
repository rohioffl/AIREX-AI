import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockAuth = vi.hoisted(() => ({
  user: {
    role: 'platform_admin',
    displayName: 'Root Admin',
  },
  logout: vi.fn(),
  organizations: [],
  tenants: [],
}))

const mockTheme = vi.hoisted(() => ({
  isDark: false,
  toggleTheme: vi.fn(),
}))

const mockToast = vi.hoisted(() => vi.fn())

const apiMocks = vi.hoisted(() => ({
  clearDLQ: vi.fn(),
  createPlatformAdmin: vi.fn(),
  createIntegrationType: vi.fn(),
  createOrganization: vi.fn(),
  deleteIntegrationType: vi.fn(),
  fetchBackendHealth: vi.fn(),
  fetchDLQ: vi.fn(),
  fetchIntegrationTypes: vi.fn(),
  fetchOrganizations: vi.fn(),
  fetchOrganizationTenants: vi.fn(),
  fetchPlatformAnalytics: vi.fn(),
  fetchPlatformAdmins: vi.fn(),
  fetchSettings: vi.fn(),
  fetchUsers: vi.fn(),
  replayDLQEntry: vi.fn(),
  updateIntegrationType: vi.fn(),
  updatePlatformAdmin: vi.fn(),
  updateSettings: vi.fn(),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockAuth,
}))

vi.mock('../context/ThemeContext', () => ({
  useTheme: () => mockTheme,
}))

vi.mock('../context/ToastContext', () => ({
  useToasts: () => ({
    addToast: mockToast,
  }),
}))

vi.mock('../components/admin/TenantWorkspaceManager', () => ({
  default: ({ mode }) => <div data-testid="tenant-workspace-manager">mode:{mode}</div>,
}))

vi.mock('../services/api', () => apiMocks)

import PlatformAdminPage from '../pages/PlatformAdminPage'

describe('PlatformAdminPage users section', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuth.organizations = []
    mockAuth.tenants = []
    apiMocks.fetchPlatformAdmins.mockResolvedValue({ items: [] })
    apiMocks.fetchPlatformAnalytics.mockResolvedValue({
      total_users: 451,
      active_users: 424,
      total_platform_admins: 2,
      active_platform_admins: 1,
      total_organizations: 1,
      active_organizations: 1,
      total_tenants: 3,
      active_tenants: 3,
      active_incidents: 0,
      critical_incidents: 0,
      failed_incidents_24h: 0,
      total_incidents_24h: 0,
      platform_error_rate_24h: 0,
      dlq_entries: 0,
      llm_circuit_breaker_open: false,
    })
    apiMocks.fetchOrganizations.mockResolvedValue([])
    apiMocks.fetchOrganizationTenants.mockResolvedValue([])
    apiMocks.fetchBackendHealth.mockResolvedValue({ status: 'ok' })
  })

  it('shows platform admins without querying tenant users', async () => {
    apiMocks.fetchPlatformAdmins.mockResolvedValue({
      items: [
        {
          id: 'platform-admin-1',
          email: 'root@example.com',
          display_name: 'Root Admin',
          is_active: true,
          role: 'platform_admin',
        },
      ],
    })

    render(
      <MemoryRouter initialEntries={['/admin?section=users']}>
        <Routes>
          <Route path="/admin" element={<PlatformAdminPage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Platform Administrators')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('root@example.com')).toBeInTheDocument()
    })

    expect(apiMocks.fetchPlatformAdmins).toHaveBeenCalledTimes(1)
    expect(apiMocks.fetchUsers).not.toHaveBeenCalled()
  })

  it('allows creating a platform admin from the users section', async () => {
    const user = userEvent.setup()
    apiMocks.createPlatformAdmin.mockResolvedValue({
      id: 'platform-admin-2',
      email: 'ops@example.com',
      display_name: 'Ops Admin',
      is_active: true,
      role: 'platform_admin',
    })
    apiMocks.fetchPlatformAdmins
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({
        items: [
          {
            id: 'platform-admin-2',
            email: 'ops@example.com',
            display_name: 'Ops Admin',
            is_active: true,
            role: 'platform_admin',
          },
        ],
      })

    render(
      <MemoryRouter initialEntries={['/admin?section=users']}>
        <Routes>
          <Route path="/admin" element={<PlatformAdminPage />} />
        </Routes>
      </MemoryRouter>
    )

    await user.click(screen.getByRole('button', { name: /add platform admin/i }))
    await user.type(screen.getByPlaceholderText(/email address/i), 'ops@example.com')
    await user.type(screen.getByPlaceholderText(/display name/i), 'Ops Admin')
    await user.type(screen.getByPlaceholderText(/^password$/i), 'StrongPass123')
    await user.click(screen.getByRole('button', { name: /create platform admin/i }))

    await waitFor(() => {
      expect(apiMocks.createPlatformAdmin).toHaveBeenCalledWith({
        email: 'ops@example.com',
        display_name: 'Ops Admin',
        password: 'StrongPass123',
      })
    })
  })

  it('uses platform inventory mode for the workspaces section', async () => {
    render(
      <MemoryRouter initialEntries={['/admin?section=workspaces']}>
        <Routes>
          <Route path="/admin" element={<PlatformAdminPage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText(/manage tenant inventory, onboarding, and organization mappings/i)).toBeInTheDocument()
    expect(screen.getByTestId('tenant-workspace-manager')).toHaveTextContent('mode:platform')
  })

  it('shows organization tenants when an organization is selected', async () => {
    const user = userEvent.setup()
    apiMocks.fetchOrganizationTenants.mockResolvedValue([
      {
        id: 'tenant-1',
        organization_id: 'org-1',
        display_name: 'AWS Test Client',
        name: 'aws-test-client',
        cloud: 'aws',
        credential_status: 'configured',
        escalation_email: 'ops@example.com',
      },
      {
        id: 'tenant-2',
        organization_id: 'org-1',
        display_name: 'GCP Test Client',
        name: 'gcp-test-client',
        cloud: 'gcp',
        credential_status: 'missing',
        escalation_email: '',
      },
    ])
    apiMocks.fetchOrganizations.mockResolvedValue([
      {
        id: 'org-1',
        name: 'Default Organization',
        slug: 'default-org',
        status: 'active',
        tenant_count: 2,
      },
    ])

    render(
      <MemoryRouter initialEntries={['/admin?section=organizations']}>
        <Routes>
          <Route path="/admin" element={<PlatformAdminPage />} />
        </Routes>
      </MemoryRouter>
    )

    await user.click(await screen.findByText('Default Organization'))

    expect(await screen.findByText('AWS Test Client')).toBeInTheDocument()
    expect(screen.getByText('GCP Test Client')).toBeInTheDocument()
    expect(screen.getByText('ops@example.com')).toBeInTheDocument()
  })
})
