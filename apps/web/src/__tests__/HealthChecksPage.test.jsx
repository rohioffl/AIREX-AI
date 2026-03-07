import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import HealthChecksPage from '../pages/HealthChecksPage'

// Mocks
vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({ isDark: true }),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { role: 'admin', username: 'test' } }),
}))

const mockDashboard = {
  summary: {
    total_targets: 5,
    healthy: 3,
    degraded: 1,
    down: 1,
    unknown: 0,
    error: 0,
    last_run_at: '2026-03-03T10:00:00Z',
    incidents_created_24h: 2,
  },
  targets: [
    {
      target_type: 'site24x7_monitor',
      target_id: 'mon-001',
      target_name: 'Web Server US',
      status: 'healthy',
      last_checked: '2026-03-03T10:00:00Z',
      anomaly_count: 0,
      latest_metrics: { response_time_ms: 120 },
      incident_id: null,
    },
    {
      target_type: 'site24x7_monitor',
      target_id: 'mon-002',
      target_name: 'API Gateway',
      status: 'degraded',
      last_checked: '2026-03-03T10:00:00Z',
      anomaly_count: 1,
      latest_metrics: { response_time_ms: 3500 },
      incident_id: null,
    },
    {
      target_type: 'site24x7_monitor',
      target_id: 'mon-003',
      target_name: 'Database Primary',
      status: 'down',
      last_checked: '2026-03-03T10:00:00Z',
      anomaly_count: 2,
      latest_metrics: { cpu_percent: 98 },
      incident_id: 'inc-linked-001',
    },
  ],
  recent_checks: [
    {
      id: 'chk-001',
      tenant_id: '00000000-0000-0000-0000-000000000000',
      target_type: 'site24x7_monitor',
      target_id: 'mon-001',
      target_name: 'Web Server US',
      status: 'healthy',
      metrics: {},
      anomalies: null,
      incident_created: false,
      incident_id: null,
      checked_at: '2026-03-03T10:00:00Z',
      duration_ms: 45.2,
      error: null,
    },
  ],
}

let mockFetchDashboard
let mockTriggerCheck

vi.mock('../services/api', () => ({
  fetchHealthCheckDashboard: (...args) => mockFetchDashboard(...args),
  triggerHealthCheck: (...args) => mockTriggerCheck(...args),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <HealthChecksPage />
    </MemoryRouter>
  )
}

describe('HealthChecksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchDashboard = vi.fn().mockResolvedValue(mockDashboard)
    mockTriggerCheck = vi.fn().mockResolvedValue({ status: 'completed' })
  })

  it('renders loading state initially', () => {
    // Make the fetch never resolve to keep loading state
    mockFetchDashboard = vi.fn().mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.getByText('Loading health checks...')).toBeInTheDocument()
  })

  it('renders dashboard after loading', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Proactive Health Checks')).toBeInTheDocument()
    })
    expect(mockFetchDashboard).toHaveBeenCalledTimes(1)
  })

  it('displays summary cards with correct counts', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Proactive Health Checks')).toBeInTheDocument()
    })
    // Summary values
    expect(screen.getByText('5')).toBeInTheDocument()  // total
    expect(screen.getByText('3')).toBeInTheDocument()  // healthy
  })

  it('displays target list with status badges', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getAllByText('Web Server US').length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getByText('API Gateway')).toBeInTheDocument()
    expect(screen.getByText('Database Primary')).toBeInTheDocument()
  })

  it('shows degraded target with anomaly count', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('API Gateway')).toBeInTheDocument()
    })
    expect(screen.getByText('1 anomaly')).toBeInTheDocument()
  })

  it('shows down target with anomaly count (plural)', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Database Primary')).toBeInTheDocument()
    })
    expect(screen.getByText('2 anomalies')).toBeInTheDocument()
  })

  it('expands target row to show details on click', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => {
      expect(screen.getAllByText('Web Server US').length).toBeGreaterThanOrEqual(1)
    })
    await user.click(screen.getAllByText('Web Server US')[0])
    expect(screen.getByText(/mon-001/)).toBeInTheDocument()
  })

  it('shows Run Now button for admin users', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Run Now')).toBeInTheDocument()
    })
  })

  it('triggers health check on Run Now click', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Run Now')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Run Now'))
    await waitFor(() => {
      expect(mockTriggerCheck).toHaveBeenCalledTimes(1)
    })
  })

  it('displays error state', async () => {
    mockFetchDashboard = vi.fn().mockRejectedValue(new Error('Network error'))
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('renders empty state when no targets', async () => {
    mockFetchDashboard = vi.fn().mockResolvedValue({
      summary: { total_targets: 0, healthy: 0, degraded: 0, down: 0, unknown: 0, error: 0 },
      targets: [],
      recent_checks: [],
    })
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/No health checks have run yet/)).toBeInTheDocument()
    })
  })

  it('filters targets by status when filter tab clicked', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => {
      expect(screen.getAllByText('Web Server US').length).toBeGreaterThanOrEqual(1)
    })
    // Click the "Down" filter
    await user.click(screen.getByText(/Down \(/))
    // Only the down target should be visible
    expect(screen.getByText('Database Primary')).toBeInTheDocument()
    // Web Server US still appears in recent checks section but not in targets
    expect(screen.queryByText('API Gateway')).not.toBeInTheDocument()
  })

  it('renders recent checks section', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Recent Checks (last 50)')).toBeInTheDocument()
    })
  })

  it('displays filter tabs with counts', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('All (3)')).toBeInTheDocument()
    })
  })

  it('shows View Incident link for target with incident', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Database Primary')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Database Primary'))
    expect(screen.getByText('View Incident')).toBeInTheDocument()
  })

  it('navigates to incident on View Incident click', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Database Primary')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Database Primary'))
    await user.click(screen.getByText('View Incident'))
    expect(mockNavigate).toHaveBeenCalledWith('/incidents/inc-linked-001')
  })

  it('displays last run time in header', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/Last run:/)).toBeInTheDocument()
    })
  })
})
