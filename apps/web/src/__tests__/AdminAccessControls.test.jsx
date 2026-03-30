import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockAddToast = vi.hoisted(() => vi.fn())

vi.mock('../context/ToastContext', () => ({
  useToasts: () => ({ addToast: mockAddToast }),
}))

const mockApi = vi.hoisted(() => ({
  fetchUsers: vi.fn(),
  fetchOrgMembers: vi.fn(),
  addOrgMember: vi.fn(),
  inviteOrgMember: vi.fn(),
  updateOrgMember: vi.fn(),
  removeOrgMember: vi.fn(),
  fetchUserAccessibleTenants: vi.fn(),
  fetchTenantMembers: vi.fn(),
  addTenantMember: vi.fn(),
  updateTenantMember: vi.fn(),
  removeTenantMember: vi.fn(),
}))

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    fetchUsers: mockApi.fetchUsers,
    fetchOrgMembers: mockApi.fetchOrgMembers,
    addOrgMember: mockApi.addOrgMember,
    inviteOrgMember: mockApi.inviteOrgMember,
    updateOrgMember: mockApi.updateOrgMember,
    removeOrgMember: mockApi.removeOrgMember,
    fetchUserAccessibleTenants: mockApi.fetchUserAccessibleTenants,
    fetchTenantMembers: mockApi.fetchTenantMembers,
    addTenantMember: mockApi.addTenantMember,
    updateTenantMember: mockApi.updateTenantMember,
    removeTenantMember: mockApi.removeTenantMember,
  }
})

import AccessMatrixView from '../components/admin/AccessMatrixView'
import TenantAccessDrawer from '../components/admin/TenantAccessDrawer'
import TenantMembersPanel from '../components/admin/TenantMembersPanel'

describe('admin access control components', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.fetchUsers.mockResolvedValue([
      { id: 'user-1', display_name: 'Ava Admin', email: 'ava@example.com' },
      { id: 'user-2', display_name: 'Omar Ops', email: 'omar@example.com' },
      { id: 'user-3', display_name: 'Tia Tenant', email: 'tia@example.com' },
    ])
    mockApi.fetchOrgMembers.mockResolvedValue([
      {
        id: 'org-member-1',
        user_id: 'user-1',
        role: 'admin',
        email: 'ava@example.com',
        display_name: 'Ava Admin',
        is_active: true,
        invitation_status: 'accepted',
      },
    ])
    mockApi.addOrgMember.mockResolvedValue({ id: 'org-member-2', user_id: 'user-2', role: 'operator' })
    mockApi.inviteOrgMember.mockResolvedValue({
      user_id: 'user-4',
      email: 'neworg@example.com',
      role: 'viewer',
      organization_id: 'org-1',
      invitation_url: 'http://localhost:5173/set-password?token=test',
      expires_at: '2026-04-03T00:00:00Z',
    })
    mockApi.updateOrgMember.mockImplementation(async (_orgId, userId, payload) => ({ id: `org-${userId}`, user_id: userId, role: payload.role }))
    mockApi.removeOrgMember.mockResolvedValue({})
    mockApi.fetchUserAccessibleTenants.mockResolvedValue([
      { id: 'tenant-1', organization_id: 'org-1', membership_role: 'admin' },
    ])
    mockApi.fetchTenantMembers.mockResolvedValue([
      { id: 'tenant-member-1', user_id: 'user-3', role: 'viewer' },
    ])
    mockApi.addTenantMember.mockResolvedValue({ id: 'tenant-member-2', user_id: 'user-2', role: 'operator' })
    mockApi.updateTenantMember.mockImplementation(async (_tenantId, userId, payload) => ({ id: `tenant-${userId}`, user_id: userId, role: payload.role }))
    mockApi.removeTenantMember.mockResolvedValue({})
  })

  it('adds and updates organization members from the access matrix', async () => {
    const user = userEvent.setup()
    const onInspectUser = vi.fn()

    render(
      <AccessMatrixView
        organization={{ id: 'org-1', name: 'Acme Cloud' }}
        tenants={[
          { id: 'tenant-1', display_name: 'Alpha', name: 'alpha', cloud: 'aws' },
          { id: 'tenant-2', display_name: 'Beta', name: 'beta', cloud: 'gcp' },
        ]}
        onInspectUser={onInspectUser}
      />
    )

    expect(await screen.findByText('Ava Admin')).toBeInTheDocument()
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByLabelText('Organization member status for Ava Admin')).toHaveTextContent('Active')
      expect(screen.getByLabelText('Access cell Ava Admin Alpha')).toHaveTextContent('admin')
      expect(screen.getByLabelText('Access cell Ava Admin Beta')).toHaveTextContent('none')
    })

    await user.click(screen.getByRole('button', { name: /add org member/i }))
    await user.selectOptions(screen.getByLabelText('Organization member user'), 'user-2')
    await user.selectOptions(screen.getByLabelText('Organization member role'), 'operator')
    await user.click(screen.getByRole('button', { name: /^add$/i }))

    expect(await screen.findByText('Omar Ops')).toBeInTheDocument()
    expect(mockApi.addOrgMember).toHaveBeenCalledWith('org-1', { user_id: 'user-2', role: 'operator' })

    await user.selectOptions(screen.getByLabelText('Organization role for Ava Admin'), 'viewer')
    await waitFor(() => {
      expect(mockApi.updateOrgMember).toHaveBeenCalledWith('org-1', 'user-1', { role: 'viewer' })
    })

    await user.click(screen.getAllByRole('button', { name: /^view$/i })[0])
    expect(onInspectUser).toHaveBeenCalled()
  })

  it('invites organization members without requiring a home tenant selection', async () => {
    const user = userEvent.setup()

    render(
      <AccessMatrixView
        organization={{ id: 'org-1', name: 'Acme Cloud' }}
        tenants={[
          { id: 'tenant-1', display_name: 'Alpha', name: 'alpha', cloud: 'aws' },
          { id: 'tenant-2', display_name: 'Beta', name: 'beta', cloud: 'gcp' },
        ]}
      />
    )

    expect(await screen.findByText('Ava Admin')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /invite org member/i }))
    await user.type(screen.getByLabelText('Org member invite email'), 'neworg@example.com')
    await user.type(screen.getByLabelText('Org member invite display name'), 'New Org User')
    await user.selectOptions(screen.getByLabelText('Invited org member role'), 'viewer')
    await user.click(screen.getByRole('button', { name: /send invite/i }))

    await waitFor(() => {
      expect(mockApi.inviteOrgMember).toHaveBeenCalledWith('org-1', {
        email: 'neworg@example.com',
        display_name: 'New Org User',
        role: 'viewer',
      })
    })
  })

  it('shows access granted when the invited email already has an account', async () => {
    const user = userEvent.setup()
    mockApi.inviteOrgMember.mockResolvedValueOnce({
      user_id: 'user-2',
      email: 'omar@example.com',
      role: 'admin',
      organization_id: 'org-1',
      home_tenant_id: 'tenant-1',
      invitation_url: null,
      expires_at: null,
      status: 'access_granted',
    })

    render(
      <AccessMatrixView
        organization={{ id: 'org-1', name: 'Acme Cloud' }}
        tenants={[
          { id: 'tenant-1', display_name: 'Alpha', name: 'alpha', cloud: 'aws' },
        ]}
      />
    )

    expect(await screen.findByText('Ava Admin')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /invite org member/i }))
    await user.type(screen.getByLabelText('Org member invite email'), 'omar@example.com')
    await user.selectOptions(screen.getByLabelText('Invited org member role'), 'admin')
    await user.click(screen.getByRole('button', { name: /send invite/i }))

    await waitFor(() => {
      expect(mockAddToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Access granted',
          message: 'omar@example.com was added to the organization',
        })
      )
    })
  })

  it('renders pending org members even when they are not in the tenant user list', async () => {
    mockApi.fetchOrgMembers.mockResolvedValueOnce([
      {
        id: 'org-member-pending',
        user_id: 'user-99',
        role: 'viewer',
        email: 'pending@example.com',
        display_name: 'Pending Org User',
        is_active: false,
        invitation_status: 'pending',
      },
    ])

    render(
      <AccessMatrixView
        organization={{ id: 'org-1', name: 'Acme Cloud' }}
        tenants={[
          { id: 'tenant-1', display_name: 'Alpha', name: 'alpha', cloud: 'aws' },
        ]}
      />
    )

    expect(await screen.findByText('Pending Org User')).toBeInTheDocument()
    expect(screen.getByLabelText('Organization member status for Pending Org User')).toHaveTextContent('Pending')
    expect(screen.getByText('pending@example.com')).toBeInTheDocument()
  })

  it('renders accessible tenants in the drawer and manages explicit access', async () => {
    const user = userEvent.setup()
    render(
      <TenantAccessDrawer
        open
        user={{ id: 'user-1', display_name: 'Ava Admin' }}
        tenants={[
          { id: 'tenant-1', name: 'alpha', display_name: 'Alpha', cloud: 'aws' },
          { id: 'tenant-2', name: 'beta', display_name: 'Beta', cloud: 'gcp' },
        ]}
        onClose={() => {}}
      />
    )

    expect(await screen.findByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
    expect(screen.getByText('Explicit admin')).toBeInTheDocument()
    expect(screen.getByText('No direct access')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Tenant access role for Beta'), 'operator')
    await user.click(screen.getByRole('button', { name: 'Assign' }))
    await waitFor(() => {
      expect(mockApi.addTenantMember).toHaveBeenCalledWith('tenant-2', { user_id: 'user-1', role: 'operator' })
    })

    await user.selectOptions(screen.getByLabelText('Tenant access role for Alpha'), 'viewer')
    await user.click(screen.getByRole('button', { name: 'Save Role' }))
    await waitFor(() => {
      expect(mockApi.updateTenantMember).toHaveBeenCalledWith('tenant-1', 'user-1', { role: 'viewer' })
    })

    await user.click(screen.getAllByRole('button', { name: 'Remove' })[0])
    await waitFor(() => {
      expect(mockApi.removeTenantMember).toHaveBeenCalledWith('tenant-1', 'user-1')
    })
  })

  it('adds and updates tenant members', async () => {
    const user = userEvent.setup()

    render(
      <TenantMembersPanel tenant={{ id: 'tenant-1', display_name: 'Alpha' }} />
    )

    expect(await screen.findByText('Tia Tenant')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /add tenant member/i }))
    await user.selectOptions(screen.getByLabelText('Tenant member user'), 'user-2')
    await user.selectOptions(screen.getByLabelText('Tenant member role'), 'operator')
    await user.click(screen.getByRole('button', { name: /add member/i }))

    expect(await screen.findByText('Omar Ops')).toBeInTheDocument()
    expect(mockApi.addTenantMember).toHaveBeenCalledWith('tenant-1', { user_id: 'user-2', role: 'operator' })

    await user.selectOptions(screen.getByLabelText('Role for Tia Tenant'), 'admin')
    await waitFor(() => {
      expect(mockApi.updateTenantMember).toHaveBeenCalledWith('tenant-1', 'user-3', { role: 'admin' })
    })
  })
})
