import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../components/admin/TenantWorkspaceManager', () => ({
  default: ({ mode }) => <div data-testid="tenant-workspace-manager">{mode}</div>,
}))

import OrganizationsAdminPage from '../pages/admin/OrganizationsAdminPage'
import TenantWorkspaceAdminPage from '../pages/admin/TenantWorkspaceAdminPage'
import IntegrationsAdminPage from '../pages/admin/IntegrationsAdminPage'

describe('admin workspace route pages', () => {
  it('renders the organizations admin page wrapper', () => {
    render(
      <MemoryRouter>
        <OrganizationsAdminPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Organization Admin')).toBeInTheDocument()
    expect(screen.getByTestId('tenant-workspace-manager')).toHaveTextContent('organizations')
  })

  it('renders the tenant workspace admin page wrapper', () => {
    render(
      <MemoryRouter>
        <TenantWorkspaceAdminPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Tenant Workspaces')).toBeInTheDocument()
    expect(screen.getByTestId('tenant-workspace-manager')).toHaveTextContent('workspace')
  })

  it('renders the integrations admin page wrapper', () => {
    render(
      <MemoryRouter>
        <IntegrationsAdminPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Monitoring Integrations')).toBeInTheDocument()
    expect(screen.getByTestId('tenant-workspace-manager')).toHaveTextContent('integrations')
  })
})
