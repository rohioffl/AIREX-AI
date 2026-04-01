import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockAuth = vi.hoisted(() => ({
  organizations: [{ id: 'org-1', name: 'Acme Cloud' }],
  activeOrganization: { id: 'org-1', name: 'Acme Cloud' },
}))

const mockApi = vi.hoisted(() => ({
  fetchAnalyticsTrends: vi.fn(),
  fetchOrganizationAnalytics: vi.fn(),
}))

// isOrgScoped drives scope automatically — default to tenant-scoped for manual-toggle tests
const mockWorkspacePath = vi.hoisted(() => ({ isOrgScoped: false }))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockAuth,
}))

vi.mock('../services/api', () => ({
  fetchAnalyticsTrends: mockApi.fetchAnalyticsTrends,
  fetchOrganizationAnalytics: mockApi.fetchOrganizationAnalytics,
}))

vi.mock('../hooks/useWorkspacePath', () => ({
  useWorkspacePath: () => mockWorkspacePath,
}))

import AnalyticsPage from '../pages/AnalyticsPage'

describe('AnalyticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockWorkspacePath.isOrgScoped = false
    mockApi.fetchAnalyticsTrends.mockResolvedValue({
      mttr_trends: [],
      resolution_rates: [],
      alert_volume: [],
      ai_accuracy: [],
    })
    mockApi.fetchOrganizationAnalytics.mockResolvedValue({
      tenant_count: 4,
      active_tenant_count: 3,
      member_count: 8,
    })
  })

  it('loads organization analytics when org scope is selected via toggle', async () => {
    const user = userEvent.setup()
    render(<AnalyticsPage />)

    expect(await screen.findByText('Analytics Dashboard')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /all org workspaces/i }))

    await waitFor(() => {
      expect(mockApi.fetchOrganizationAnalytics).toHaveBeenCalledWith('org-1')
    })
    expect(await screen.findByText('Total Workspaces')).toBeInTheDocument()
    expect(screen.getByText('Active Workspaces')).toBeInTheDocument()
    expect(screen.getByText('Org Members')).toBeInTheDocument()
  })

  it('auto-loads org analytics when URL is org-scoped', async () => {
    mockWorkspacePath.isOrgScoped = true
    render(<AnalyticsPage />)

    expect(await screen.findByText('Analytics Dashboard')).toBeInTheDocument()
    // Toggle is hidden when org-scoped
    expect(screen.queryByRole('button', { name: /all org workspaces/i })).not.toBeInTheDocument()
    // Org analytics load automatically
    await waitFor(() => {
      expect(mockApi.fetchOrganizationAnalytics).toHaveBeenCalledWith('org-1')
    })
    expect(await screen.findByText('Total Workspaces')).toBeInTheDocument()
  })
})
