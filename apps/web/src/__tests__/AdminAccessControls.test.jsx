import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockAddToast = vi.hoisted(() => vi.fn())

vi.mock('../context/ToastContext', () => ({
  useToasts: () => ({ addToast: mockAddToast }),
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'user-1', userId: 'user-1', email: 'ava@example.com', displayName: 'Ava Admin' },
  }),
}))

const mockApi = vi.hoisted(() => ({
  fetchUsers: vi.fn(),
  fetchOrgMembers: vi.fn(),
  inviteOrgMember: vi.fn(),
  resendOrgInvitation: vi.fn(),
  updateOrgMember: vi.fn(),
  removeOrgMember: vi.fn(),
  fetchUserAccessibleTenants: vi.fn(),
  fetchTenantMembers: vi.fn(),
  inviteTenantUser: vi.fn(),
  resendTenantInvitation: vi.fn(),
  updateTenantMember: vi.fn(),
  removeTenantMember: vi.fn(),
}))

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api')
  return {
    ...actual,
    fetchUsers: mockApi.fetchUsers,
    fetchOrgMembers: mockApi.fetchOrgMembers,
    inviteOrgMember: mockApi.inviteOrgMember,
    resendOrgInvitation: mockApi.resendOrgInvitation,
    updateOrgMember: mockApi.updateOrgMember,
    removeOrgMember: mockApi.removeOrgMember,
    fetchUserAccessibleTenants: mockApi.fetchUserAccessibleTenants,
    fetchTenantMembers: mockApi.fetchTenantMembers,
    inviteTenantUser: mockApi.inviteTenantUser,
    resendTenantInvitation: mockApi.resendTenantInvitation,
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
      {
        id: 'org-member-2',
        user_id: 'user-2',
        role: 'operator',
        email: 'omar@example.com',
        display_name: 'Omar Ops',
        is_active: true,
        invitation_status: 'accepted',
      },
    ])
    mockApi.inviteOrgMember.mockResolvedValue({
      user_id: 'user-4',
      email: 'neworg@example.com',
      role: 'viewer',
      organization_id: 'org-1',
      invitation_url: 'http://localhost:5173/set-password?token=test',
      expires_at: '2026-04-03T00:00:00Z',
    })
    mockApi.updateOrgMember.mockImplementation(async (_orgId, userId, payload) => ({ id: `org-${userId}`, user_id: userId, role: payload.role }))
    mockApi.resendOrgInvitation.mockResolvedValue({ message: 'Invitation resent', email: 'omar@example.com', delivery_mode: 'accept_invitation', expires_at: '2026-04-03T00:00:00Z' })
    mockApi.removeOrgMember.mockResolvedValue({})
    mockApi.fetchUserAccessibleTenants.mockResolvedValue([
      { id: 'tenant-1', organization_id: 'org-1', membership_role: 'admin' },
    ])
    mockApi.fetchTenantMembers.mockResolvedValue([
      { id: 'tenant-member-1', user_id: 'user-3', role: 'viewer', display_name: 'Tia Tenant', email: 'tia@example.com' },
    ])
    mockApi.inviteTenantUser.mockResolvedValue({
      user_id: 'user-9',
      email: 'invitee@example.com',
      role: 'operator',
      invitation_url: 'http://localhost:5173/set-password?token=workspace-test',
      expires_at: '2026-04-03T00:00:00Z',
    })
    mockApi.resendTenantInvitation.mockResolvedValue({ message: 'Invitation resent', email: 'tia@example.com', expires_at: '2026-04-03T00:00:00Z' })
    mockApi.updateTenantMember.mockImplementation(async (_tenantId, userId, payload) => ({ id: `tenant-${userId}`, user_id: userId, role: payload.role }))
    mockApi.removeTenantMember.mockResolvedValue({})
  })

  it('updates organization members from the access matrix', async () => {
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
    await waitFor(() => {
      expect(screen.getByLabelText('Organization member status for Ava Admin')).toHaveTextContent('Active')
    })

    expect(screen.queryByRole('button', { name: /add org member/i })).not.toBeInTheDocument()
    expect(screen.getByText('Omar Ops')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Organization role for Omar Ops'), 'viewer')
    await waitFor(() => {
      expect(mockApi.updateOrgMember).toHaveBeenCalledWith('org-1', 'user-2', { role: 'viewer' })
    })

    await user.click(screen.getAllByRole('button', { name: /^view$/i })[0])
    expect(onInspectUser).toHaveBeenCalled()
  })

  it('blocks self role edits and self removal in organization members', async () => {
    render(
      <AccessMatrixView
        organization={{ id: 'org-1', name: 'Acme Cloud' }}
        tenants={[
          { id: 'tenant-1', display_name: 'Alpha', name: 'alpha', cloud: 'aws' },
        ]}
      />
    )

    expect(await screen.findByText('Ava Admin')).toBeInTheDocument()

    expect(screen.getByLabelText('Organization role for Ava Admin')).toBeDisabled()
    expect(screen.getAllByRole('button', { name: /remove organization member/i })[0]).toBeDisabled()
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

  it('allows org invites even when the organization has no workspaces yet', async () => {
    const user = userEvent.setup()

    render(
      <AccessMatrixView
        organization={{ id: 'org-1', name: 'Acme Cloud' }}
        tenants={[]}
      />
    )

    expect(await screen.findByText('Ava Admin')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /invite org member/i }))
    expect(screen.getByText('Org access is ready before workspace setup')).toBeInTheDocument()
    expect(screen.queryByText('Create a workspace first')).not.toBeInTheDocument()

    await user.type(screen.getByLabelText('Org member invite email'), 'emptyorg@example.com')
    await user.selectOptions(screen.getByLabelText('Invited org member role'), 'operator')
    await user.click(screen.getByRole('button', { name: /send invite/i }))

    await waitFor(() => {
      expect(mockApi.inviteOrgMember).toHaveBeenCalledWith('org-1', {
        email: 'emptyorg@example.com',
        display_name: '',
        role: 'operator',
      })
    })
  })

  it('keeps existing accounts pending until they accept the org invite', async () => {
    const user = userEvent.setup()
    mockApi.inviteOrgMember.mockResolvedValueOnce({
      user_id: 'user-2',
      email: 'omar@example.com',
      role: 'admin',
      organization_id: 'org-1',
      home_tenant_id: 'tenant-1',
      invitation_url: 'http://localhost:5173/set-password?token=existing-user-token',
      expires_at: '2026-04-03T00:00:00Z',
      status: 'invited',
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
          title: 'Invitation sent',
          message: 'Org invite sent to omar@example.com',
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

  it('resends pending organization invitations', async () => {
    const user = userEvent.setup()
    mockApi.fetchOrgMembers.mockResolvedValueOnce([
      {
        id: 'org-member-pending',
        user_id: 'user-2',
        role: 'viewer',
        email: 'omar@example.com',
        display_name: 'Omar Ops',
        is_active: true,
        invitation_status: 'pending',
      },
    ])

    render(
      <AccessMatrixView
        organization={{ id: 'org-1', name: 'Acme Cloud' }}
        tenants={[]}
      />
    )

    expect(await screen.findByText('Omar Ops')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /resend/i }))

    await waitFor(() => {
      expect(mockApi.resendOrgInvitation).toHaveBeenCalledWith('org-1', 'user-2')
    })
  })

  it('renders accessible workspaces in the drawer and manages explicit access only', async () => {
    const user = userEvent.setup()
    render(
      <TenantAccessDrawer
        open
        user={{ id: 'user-3', display_name: 'Tia Tenant' }}
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
    expect(screen.queryByRole('button', { name: 'Assign' })).not.toBeInTheDocument()
    expect(screen.getByText(/invite-only/i)).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Workspace access role for Alpha'), 'viewer')
    await user.click(screen.getByRole('button', { name: 'Save Role' }))
    await waitFor(() => {
      expect(mockApi.updateTenantMember).toHaveBeenCalledWith('tenant-1', 'user-3', { role: 'viewer' })
    })

    await user.click(screen.getAllByRole('button', { name: 'Remove' })[0])
    await waitFor(() => {
      expect(mockApi.removeTenantMember).toHaveBeenCalledWith('tenant-1', 'user-3')
    })
  })

  it('invites and updates workspace members', async () => {
    const user = userEvent.setup()

    render(
      <TenantMembersPanel tenant={{ id: 'tenant-1', display_name: 'Alpha' }} />
    )

    expect(await screen.findByText('Tia Tenant')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /add workspace member/i })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /invite workspace user/i }))
    await user.type(screen.getByPlaceholderText('user@example.com'), 'invitee@example.com')
    await user.selectOptions(screen.getByLabelText('Invited user role'), 'operator')
    await user.click(screen.getByRole('button', { name: /send invite/i }))
    await waitFor(() => {
      expect(mockApi.inviteTenantUser).toHaveBeenCalledWith('tenant-1', {
        email: 'invitee@example.com',
        display_name: '',
        role: 'operator',
      })
    })

    await user.selectOptions(screen.getByLabelText('Role for Tia Tenant'), 'admin')
    await waitFor(() => {
      expect(mockApi.updateTenantMember).toHaveBeenCalledWith('tenant-1', 'user-3', { role: 'admin' })
    })
  })

  it('shows a dialog when workspace access already exists through the organization', async () => {
    const user = userEvent.setup()
    mockApi.inviteTenantUser.mockResolvedValueOnce({
      user_id: 'user-2',
      email: 'omar@example.com',
      role: 'viewer',
      invitation_url: null,
      expires_at: null,
      status: 'already_has_access',
    })

    render(
      <TenantMembersPanel tenant={{ id: 'tenant-1', display_name: 'Alpha' }} />
    )

    expect(await screen.findByText('Tia Tenant')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /invite workspace user/i }))
    await user.type(screen.getByPlaceholderText('user@example.com'), 'omar@example.com')
    await user.click(screen.getByRole('button', { name: /send invite/i }))

    expect(await screen.findByText('Access already available')).toBeInTheDocument()
    expect(
      screen.getByText(/already has access to this workspace through the organization/i)
    ).toBeInTheDocument()
  })

  it('blocks self role edits and self removal in workspace members', async () => {
    mockApi.fetchTenantMembers.mockResolvedValueOnce([
      {
        id: 'tenant-member-self',
        user_id: 'user-1',
        role: 'admin',
        email: 'ava@example.com',
        display_name: 'Ava Admin',
        is_active: true,
      },
    ])

    render(
      <TenantMembersPanel tenant={{ id: 'tenant-1', display_name: 'Alpha' }} />
    )

    expect(await screen.findByText('Ava Admin')).toBeInTheDocument()

    expect(screen.getByLabelText('Role for Ava Admin')).toBeDisabled()
    expect(screen.getByRole('button', { name: /remove member/i })).toBeDisabled()
  })

  it('resends pending workspace invitations', async () => {
    const user = userEvent.setup()
    mockApi.fetchTenantMembers.mockResolvedValueOnce([
      {
        id: 'tenant-member-1',
        user_id: 'user-3',
        role: 'viewer',
        email: 'tia@example.com',
        display_name: 'Tia Tenant',
        is_active: false,
      },
    ])

    render(
      <TenantMembersPanel tenant={{ id: 'tenant-1', display_name: 'Alpha' }} />
    )

    expect(await screen.findByText('Tia Tenant')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /resend/i }))

    await waitFor(() => {
      expect(mockApi.resendTenantInvitation).toHaveBeenCalledWith('tenant-1', 'user-3')
    })
  })
})
