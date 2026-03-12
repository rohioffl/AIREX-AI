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
let mockFetchMonitorInventory

vi.mock('../services/api', () => ({
  fetchHealthCheckDashboard: (...args) => mockFetchDashboard(...args),
  triggerHealthCheck: (...args) => mockTriggerCheck(...args),
  fetchMonitorInventory: (...args) => mockFetchMonitorInventory(...args),
}))

const mockMonitorInventory = {
  site24x7_enabled: true,
  total: 3,
  last_synced_at: '2026-03-03T10:00:00Z',
  status_summary: {
    total_monitors: 3,
    down: 1,
    critical: 1,
    trouble: 0,
    up: 1,
    confirmed_anomalies: 0,
    maintenance: 0,
    discovery_in_progress: 0,
    configuration_error: 0,
    suspended: 0,
  },
  monitors: [
    {
      monitor_id: 'mon-001',
      monitor_name: 'Web Server US',
      monitor_type: 'URL',
      current_status: 'healthy',
      site24x7_status_label: 'up',
      last_checked_at: '2026-03-03T10:00:00Z',
      last_incident_id: null,
    },
    {
      monitor_id: 'mon-002',
      monitor_name: 'API Gateway',
      monitor_type: 'API',
      current_status: 'degraded',
      site24x7_status_label: 'critical',
      last_checked_at: '2026-03-03T10:00:00Z',
      last_incident_id: null,
    },
    {
      monitor_id: 'mon-003',
      monitor_name: 'Database Primary',
      monitor_type: 'SERVER',
      current_status: 'down',
      site24x7_status_label: 'down',
      last_checked_at: '2026-03-03T10:00:00Z',
      last_incident_id: 'inc-linked-001',
    },
  ],
}

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
    mockFetchMonitorInventory = vi.fn().mockResolvedValue(mockMonitorInventory)
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
      expect(screen.getByText('Site24x7 Health Checks')).toBeInTheDocument()
    })
    expect(mockFetchDashboard).toHaveBeenCalledTimes(1)
    expect(mockFetchMonitorInventory).toHaveBeenCalledTimes(1)
  })

  it('displays summary cards with correct counts', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('AIREX Proactive Snapshot (Last Run)')).toBeInTheDocument()
    })
    expect(screen.getByText('Evaluated')).toBeInTheDocument()
    expect(screen.getByText('Incidents (24h)')).toBeInTheDocument()
    expect(screen.getAllByText('5').length).toBeGreaterThan(0)
    expect(screen.getAllByText('3').length).toBeGreaterThan(0)
  })

  it('displays target list with status badges', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Site24x7 Live Targets (1)')).toBeInTheDocument()
    })
    expect(screen.getAllByText('Database Primary').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Down').length).toBeGreaterThan(0)
  })

  it('shows critical targets when critical filter is selected', async () => {
    renderPage()
    const user = userEvent.setup()
    await waitFor(() => {
      expect(screen.getByText('Critical (1)')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Critical (1)'))
    expect(screen.getAllByText('API Gateway').length).toBeGreaterThan(0)
  })

  it('shows down target in the default down filter', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getAllByText('Database Primary').length).toBeGreaterThan(0)
    })
    expect(screen.getByText('Site24x7 Live Targets (1)')).toBeInTheDocument()
  })

  it('expands target row to show details on click', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => {
      expect(screen.getAllByText('Database Primary').length).toBeGreaterThan(0)
    })
    await user.click(screen.getAllByText('Database Primary')[0])
    expect(screen.getByText(/mon-003/)).toBeInTheDocument()
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
    mockFetchMonitorInventory = vi.fn().mockResolvedValue({
      ...mockMonitorInventory,
      total: 0,
      status_summary: { ...mockMonitorInventory.status_summary, total_monitors: 0, down: 0, critical: 0, up: 0 },
      monitors: [],
    })
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('No targets match the selected live status filter.')).toBeInTheDocument()
    })
  })

  it('filters targets by status when filter tab clicked', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Up (1)')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Up (1)'))
    expect(screen.getByText('Site24x7 Live Targets (1)')).toBeInTheDocument()
    expect(screen.getAllByText('Web Server US').length).toBeGreaterThan(0)
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
    expect(screen.getByText('Down (1)')).toBeInTheDocument()
    expect(screen.getByText('Critical (1)')).toBeInTheDocument()
  })

  it('shows View Incident link for target with incident', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => {
      expect(screen.getAllByText('Database Primary').length).toBeGreaterThan(0)
    })
    await user.click(screen.getAllByText('Database Primary')[0])
    expect(screen.getByText('View Incident')).toBeInTheDocument()
  })

  it('navigates to incident on View Incident click', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => {
      expect(screen.getAllByText('Database Primary').length).toBeGreaterThan(0)
    })
    await user.click(screen.getAllByText('Database Primary')[0])
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
