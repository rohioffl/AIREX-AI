import { render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockUseAuth = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}))

import RequireRole from '../components/common/RequireRole'

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname}</div>
}

function renderGuard(ui, initialEntries = ['/admin']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <LocationDisplay />
      {ui}
    </MemoryRouter>
  )
}

describe('RequireRole access policies', () => {
  beforeEach(() => {
    mockUseAuth.mockReset()
  })

  it('allows platform admin access to the platform admin root', () => {
    mockUseAuth.mockReturnValue({
      user: { role: 'platform_admin' },
      loading: false,
      organizationMemberships: [],
      tenantMemberships: [],
      activeOrganization: null,
      activeTenantId: null,
    })

    renderGuard(
      <RequireRole access="platform_admin">
        <div>allowed</div>
      </RequireRole>
    )

    expect(screen.getByText('allowed')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/admin')
  })

  it('redirects org admins away from the platform admin root', () => {
    mockUseAuth.mockReturnValue({
      user: { role: 'operator' },
      loading: false,
      organizationMemberships: [{ id: 'org-1', role: 'org_admin' }],
      tenantMemberships: [],
      activeOrganization: { id: 'org-1', role: 'org_admin' },
      activeTenantId: 'tenant-1',
    })

    renderGuard(
      <RequireRole access="platform_admin">
        <div>blocked</div>
      </RequireRole>
    )

    expect(screen.queryByText('blocked')).not.toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/dashboard')
  })

  it('allows organization admin routes from membership context', () => {
    mockUseAuth.mockReturnValue({
      user: { role: 'operator' },
      loading: false,
      organizationMemberships: [{ id: 'org-1', role: 'org_admin' }],
      tenantMemberships: [],
      activeOrganization: { id: 'org-1', role: 'org_admin' },
      activeTenantId: 'tenant-1',
    })

    renderGuard(
      <RequireRole access="organizations_admin">
        <div>org admin page</div>
      </RequireRole>,
      ['/admin/organizations']
    )

    expect(screen.getByText('org admin page')).toBeInTheDocument()
  })

  it('allows tenant admin routes from active tenant membership', () => {
    mockUseAuth.mockReturnValue({
      user: { role: 'viewer' },
      loading: false,
      organizationMemberships: [],
      tenantMemberships: [{ id: 'tenant-9', role: 'tenant_admin' }],
      activeOrganization: { id: 'org-1', role: 'tenant_member' },
      activeTenantId: 'tenant-9',
    })

    renderGuard(
      <RequireRole access="tenant_admin">
        <div>tenant admin page</div>
      </RequireRole>,
      ['/admin/workspaces']
    )

    expect(screen.getByText('tenant admin page')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/admin/workspaces')
  })
})
