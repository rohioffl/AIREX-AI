import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import CorrelationGroup from '../components/incident/CorrelationGroup'

// Mock ThemeContext
vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({ isDark: true }),
}))

// Mock formatters
vi.mock('../utils/formatters', () => ({
  formatTimestamp: (ts) => ts,
  formatDuration: (d) => `${d}s`,
  formatRelativeTime: () => '2m ago',
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

const baseIncident = {
  id: 'inc-1',
  correlation_group_id: 'abc123',
  correlated_incidents: [
    {
      id: 'inc-2',
      alert_type: 'cpu_high',
      state: 'INVESTIGATING',
      severity: 'HIGH',
      title: '[DOWN] Server-B — CPU at 98%',
      host_key: '10.0.0.2',
      created_at: '2026-03-01T12:01:00Z',
    },
    {
      id: 'inc-3',
      alert_type: 'cpu_high',
      state: 'RESOLVED',
      severity: 'MEDIUM',
      title: '[DOWN] Server-C — CPU at 85%',
      host_key: '10.0.0.3',
      created_at: '2026-03-01T12:02:00Z',
    },
  ],
  correlation_summary: {
    group_id: 'abc123',
    alert_type: 'cpu_high',
    incident_count: 3,
    affected_hosts: 3,
    host_keys: ['10.0.0.1', '10.0.0.2', '10.0.0.3'],
    states: { INVESTIGATING: 1, RESOLVED: 1, RECEIVED: 1 },
    severities: { HIGH: 2, MEDIUM: 1 },
    first_seen: '2026-03-01T12:00:00Z',
    last_seen: '2026-03-01T12:02:00Z',
    span_seconds: 120,
  },
}

function renderWithRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('CorrelationGroup', () => {
  it('renders nothing when no correlation group', () => {
    const incident = { id: 'inc-1', correlated_incidents: [] }
    const { container } = renderWithRouter(<CorrelationGroup incident={incident} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing when incident is null', () => {
    const { container } = renderWithRouter(<CorrelationGroup incident={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders the header with incident and host counts', () => {
    renderWithRouter(<CorrelationGroup incident={baseIncident} />)
    expect(screen.getByText('Cross-Host Correlation')).toBeInTheDocument()
    expect(screen.getByText('3 incidents across 3 hosts')).toBeInTheDocument()
  })

  it('shows time span badge', () => {
    renderWithRouter(<CorrelationGroup incident={baseIncident} />)
    expect(screen.getByText('2m span')).toBeInTheDocument()
  })

  it('expands on click to show correlated incidents', async () => {
    const user = userEvent.setup()
    renderWithRouter(<CorrelationGroup incident={baseIncident} />)

    // Initially collapsed
    expect(screen.queryByText('[DOWN] Server-B — CPU at 98%')).not.toBeInTheDocument()

    // Click to expand
    await user.click(screen.getByLabelText('Toggle correlation group'))

    // Now shows correlated incidents
    expect(screen.getByText('[DOWN] Server-B — CPU at 98%')).toBeInTheDocument()
    expect(screen.getByText('[DOWN] Server-C — CPU at 85%')).toBeInTheDocument()
  })

  it('shows affected host keys when expanded', async () => {
    const user = userEvent.setup()
    renderWithRouter(<CorrelationGroup incident={baseIncident} />)

    await user.click(screen.getByLabelText('Toggle correlation group'))

    // Host keys appear in summary badges and possibly in incident items
    expect(screen.getByText('10.0.0.1')).toBeInTheDocument()
    // 10.0.0.2 and 10.0.0.3 appear in both summary and incident list
    expect(screen.getAllByText('10.0.0.2').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('10.0.0.3').length).toBeGreaterThanOrEqual(1)
  })

  it('navigates to correlated incident on click', async () => {
    const user = userEvent.setup()
    renderWithRouter(<CorrelationGroup incident={baseIncident} />)

    await user.click(screen.getByLabelText('Toggle correlation group'))
    await user.click(screen.getByText('[DOWN] Server-B — CPU at 98%'))

    expect(mockNavigate).toHaveBeenCalledWith('/incidents/inc-2')
  })

  it('collapses on second click', async () => {
    const user = userEvent.setup()
    renderWithRouter(<CorrelationGroup incident={baseIncident} />)

    // Expand
    await user.click(screen.getByLabelText('Toggle correlation group'))
    expect(screen.getByText('[DOWN] Server-B — CPU at 98%')).toBeInTheDocument()

    // Collapse
    await user.click(screen.getByLabelText('Toggle correlation group'))
    expect(screen.queryByText('[DOWN] Server-B — CPU at 98%')).not.toBeInTheDocument()
  })

  it('renders without summary (graceful fallback)', () => {
    const incident = {
      ...baseIncident,
      correlation_summary: null,
    }
    renderWithRouter(<CorrelationGroup incident={incident} />)
    // Falls back to correlated_incidents.length + 1
    expect(screen.getByText('Cross-Host Correlation')).toBeInTheDocument()
  })

  it('shows seconds span for short durations', () => {
    const incident = {
      ...baseIncident,
      correlation_summary: {
        ...baseIncident.correlation_summary,
        span_seconds: 45,
      },
    }
    renderWithRouter(<CorrelationGroup incident={incident} />)
    expect(screen.getByText('45s span')).toBeInTheDocument()
  })
})
