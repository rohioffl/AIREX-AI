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

vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockAuth,
}))

vi.mock('../services/api', () => ({
  fetchAnalyticsTrends: mockApi.fetchAnalyticsTrends,
  fetchOrganizationAnalytics: mockApi.fetchOrganizationAnalytics,
}))

import AnalyticsPage from '../pages/AnalyticsPage'

describe('AnalyticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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

  it('loads organization analytics when org scope is selected', async () => {
    const user = userEvent.setup()
    render(<AnalyticsPage />)

    expect(await screen.findByText('Analytics Dashboard')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /all org tenants/i }))

    await waitFor(() => {
      expect(mockApi.fetchOrganizationAnalytics).toHaveBeenCalledWith('org-1')
    })
    expect(await screen.findByText('Total Tenants')).toBeInTheDocument()
    expect(screen.getByText('Active Tenants')).toBeInTheDocument()
    expect(screen.getByText('Org Members')).toBeInTheDocument()
  })
})
