import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
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

describe('Layout workspace switcher', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.fetchIncidents.mockResolvedValue({ items: [] })
    mockApi.fetchUserAccessibleTenants.mockResolvedValue([
      {
        id: 'tenant-1',
        name: 'alpha',
        display_name: 'Alpha',
        cloud: 'aws',
        organization_id: 'org-1',
        membership_role: 'admin',
      },
      {
        id: 'tenant-2',
        name: 'beta',
        display_name: 'Beta',
        cloud: 'gcp',
        organization_id: 'org-1',
        membership_role: null,
      },
    ])
  })

  it('loads accessible tenants and switches from the sidebar', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Layout>
          <div>content</div>
        </Layout>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(mockApi.fetchUserAccessibleTenants).toHaveBeenCalledWith('user-1')
    })

    await user.click(screen.getByRole('button', { name: /acme cloud/i }))
    expect(await screen.findByText('Switch Workspace')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('inherited')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /beta/i }))
    await waitFor(() => {
      expect(mockSwitchTenant).toHaveBeenCalledWith('tenant-2')
    })
  })
})
