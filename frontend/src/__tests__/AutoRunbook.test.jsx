import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AutoRunbook from '../components/incident/AutoRunbook'

// Mock ThemeContext
vi.mock('../context/ThemeContext', () => ({
  useTheme: () => ({ isDark: true }),
}))

// Mock formatters
vi.mock('../utils/formatters', () => ({
  formatTimestamp: (ts) => ts,
  formatDuration: (d) => `${d}s`,
  formatRelativeTime: (t) => t,
}))

// Mock API
const mockFetchAutoRunbook = vi.fn()
vi.mock('../services/api', () => ({
  fetchAutoRunbook: (...args) => mockFetchAutoRunbook(...args),
}))

const resolvedIncident = {
  id: 'inc-1',
  state: 'RESOLVED',
  meta: {
    _auto_runbook_source_id: 'src-123',
    _auto_runbook_generated_at: '2026-03-01T12:00:00Z',
  },
}

const mockRunbookData = {
  incident_id: 'inc-1',
  source_id: 'src-123',
  alert_type: 'cpu_high',
  title: 'Auto-Runbook: cpu_high',
  content: '# CPU High Runbook\n\n## Symptoms\n- CPU usage above 90%\n\n## Resolution Steps\n1. Check top processes\n2. Restart service',
  generated_at: '2026-03-01T12:00:00Z',
  resolution_type: 'auto',
  chunk_count: 2,
}

describe('AutoRunbook', () => {
  beforeEach(() => {
    mockFetchAutoRunbook.mockReset()
  })

  it('renders nothing when incident is not resolved', () => {
    const incident = { ...resolvedIncident, state: 'INVESTIGATING' }
    const { container } = render(<AutoRunbook incident={incident} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing when no auto runbook source id', () => {
    const incident = { ...resolvedIncident, meta: {} }
    const { container } = render(<AutoRunbook incident={incident} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing when incident is null', () => {
    const { container } = render(<AutoRunbook incident={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders the header with Available badge', () => {
    render(<AutoRunbook incident={resolvedIncident} />)
    expect(screen.getByText('Auto-Generated Runbook')).toBeInTheDocument()
    expect(screen.getByText('Available')).toBeInTheDocument()
  })

  it('shows generated_at timestamp', () => {
    render(<AutoRunbook incident={resolvedIncident} />)
    expect(screen.getByText('2026-03-01T12:00:00Z')).toBeInTheDocument()
  })

  it('fetches and displays runbook on expand', async () => {
    const user = userEvent.setup()
    mockFetchAutoRunbook.mockResolvedValue(mockRunbookData)

    render(<AutoRunbook incident={resolvedIncident} />)

    await user.click(screen.getByLabelText('Toggle auto-generated runbook'))

    // Should show loading first
    await waitFor(() => {
      expect(mockFetchAutoRunbook).toHaveBeenCalledWith('inc-1')
    })

    // Then show content
    await waitFor(() => {
      expect(screen.getByText(/CPU High Runbook/)).toBeInTheDocument()
    })

    // Footer info
    expect(screen.getByText('2 chunks indexed in RAG')).toBeInTheDocument()
    expect(screen.getByText('Alert type: cpu_high')).toBeInTheDocument()
  })

  it('shows error when fetch fails', async () => {
    const user = userEvent.setup()
    mockFetchAutoRunbook.mockRejectedValue({
      response: { data: { detail: 'Runbook chunks not found' } },
    })

    render(<AutoRunbook incident={resolvedIncident} />)

    await user.click(screen.getByLabelText('Toggle auto-generated runbook'))

    await waitFor(() => {
      expect(screen.getByText('Runbook chunks not found')).toBeInTheDocument()
    })
  })

  it('does not refetch on second expand', async () => {
    const user = userEvent.setup()
    mockFetchAutoRunbook.mockResolvedValue(mockRunbookData)

    render(<AutoRunbook incident={resolvedIncident} />)

    // First expand
    await user.click(screen.getByLabelText('Toggle auto-generated runbook'))
    await waitFor(() => {
      expect(screen.getByText(/CPU High Runbook/)).toBeInTheDocument()
    })

    // Collapse
    await user.click(screen.getByLabelText('Toggle auto-generated runbook'))

    // Second expand — should not refetch
    await user.click(screen.getByLabelText('Toggle auto-generated runbook'))

    expect(mockFetchAutoRunbook).toHaveBeenCalledTimes(1)
  })

  it('collapses on second click', async () => {
    const user = userEvent.setup()
    mockFetchAutoRunbook.mockResolvedValue(mockRunbookData)

    render(<AutoRunbook incident={resolvedIncident} />)

    await user.click(screen.getByLabelText('Toggle auto-generated runbook'))
    await waitFor(() => {
      expect(screen.getByText(/CPU High Runbook/)).toBeInTheDocument()
    })

    await user.click(screen.getByLabelText('Toggle auto-generated runbook'))
    expect(screen.queryByText(/CPU High Runbook/)).not.toBeInTheDocument()
  })
})
