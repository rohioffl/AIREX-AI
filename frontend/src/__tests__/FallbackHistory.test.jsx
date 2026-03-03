import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FallbackHistory from '../components/incident/FallbackHistory'

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

const baseMeta = {
  recommendation: {
    proposed_action: 'scale_up_instances',
    confidence: 0.7,
    risk_level: 'LOW',
  },
  _original_proposed_action: 'restart_service',
  _is_fallback: true,
  _fallback_from: 'restart_service',
  _fallback_history: [
    {
      action: 'restart_service',
      status: 'verification_failed',
      reason: 'Verification check returned False for restart_service',
      attempted_at: '2026-03-01T12:00:00Z',
    },
  ],
}

describe('FallbackHistory', () => {
  it('renders nothing when no fallback history and not a fallback', () => {
    const incident = { meta: { recommendation: { proposed_action: 'restart_service' } } }
    const { container } = render(<FallbackHistory incident={incident} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing when incident is null', () => {
    const { container } = render(<FallbackHistory incident={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders the header with fallback count badge', () => {
    const incident = { meta: baseMeta }
    render(<FallbackHistory incident={incident} />)
    expect(screen.getByText('Fallback History')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('shows "Using fallback action" badge when isFallback is true', () => {
    const incident = { meta: baseMeta }
    render(<FallbackHistory incident={incident} />)
    expect(screen.getByText('Using fallback action')).toBeInTheDocument()
  })

  it('does not show "Using fallback action" badge when isFallback is false', () => {
    const incident = {
      meta: {
        ...baseMeta,
        _is_fallback: false,
      },
    }
    render(<FallbackHistory incident={incident} />)
    expect(screen.queryByText('Using fallback action')).not.toBeInTheDocument()
  })

  it('expands on click to show history entries', async () => {
    const user = userEvent.setup()
    const incident = { meta: baseMeta }
    render(<FallbackHistory incident={incident} />)

    // Initially collapsed — no action names visible
    expect(screen.queryByText('restart_service')).not.toBeInTheDocument()

    // Click to expand
    await user.click(screen.getByLabelText('Toggle fallback history'))

    // Now shows the failed action
    expect(screen.getByText('Verification Failed')).toBeInTheDocument()
  })

  it('shows original action with strikethrough and current action', async () => {
    const user = userEvent.setup()
    const incident = { meta: baseMeta }
    render(<FallbackHistory incident={incident} />)

    await user.click(screen.getByLabelText('Toggle fallback history'))

    // Original action (struck through) and current action should be visible
    const restartEls = screen.getAllByText('restart_service')
    // The first one is in the flow summary with strikethrough
    const originalEl = restartEls[0]
    expect(originalEl).toBeInTheDocument()
    expect(originalEl.style.textDecoration).toBe('line-through')

    expect(screen.getByText('scale_up_instances')).toBeInTheDocument()
    expect(screen.getByText('(current)')).toBeInTheDocument()
  })

  it('shows failure reason in expanded view', async () => {
    const user = userEvent.setup()
    const incident = { meta: baseMeta }
    render(<FallbackHistory incident={incident} />)

    await user.click(screen.getByLabelText('Toggle fallback history'))
    expect(screen.getByText('Verification check returned False for restart_service')).toBeInTheDocument()
  })

  it('renders multiple fallback history entries', async () => {
    const user = userEvent.setup()
    const incident = {
      meta: {
        ...baseMeta,
        recommendation: {
          proposed_action: 'clear_cache',
          confidence: 0.5,
          risk_level: 'LOW',
        },
        _fallback_history: [
          {
            action: 'restart_service',
            status: 'verification_failed',
            reason: 'Verification failed',
            attempted_at: '2026-03-01T12:00:00Z',
          },
          {
            action: 'scale_up_instances',
            status: 'verification_failed',
            reason: 'Verification failed again',
            attempted_at: '2026-03-01T12:05:00Z',
          },
        ],
      },
    }
    render(<FallbackHistory incident={incident} />)
    // Badge should show 2
    expect(screen.getByText('2')).toBeInTheDocument()

    await user.click(screen.getByLabelText('Toggle fallback history'))
    expect(screen.getByText('Verification failed')).toBeInTheDocument()
    expect(screen.getByText('Verification failed again')).toBeInTheDocument()
  })

  it('renders policy_rejected entries with correct label', async () => {
    const user = userEvent.setup()
    const incident = {
      meta: {
        ...baseMeta,
        _fallback_history: [
          {
            action: 'dangerous_action',
            status: 'policy_rejected',
            reason: 'Policy blocked: too dangerous',
            attempted_at: '2026-03-01T12:00:00Z',
          },
        ],
      },
    }
    render(<FallbackHistory incident={incident} />)

    await user.click(screen.getByLabelText('Toggle fallback history'))
    expect(screen.getByText('Policy Rejected')).toBeInTheDocument()
    expect(screen.getByText('Policy blocked: too dangerous')).toBeInTheDocument()
  })

  it('collapses on second click', async () => {
    const user = userEvent.setup()
    const incident = { meta: baseMeta }
    render(<FallbackHistory incident={incident} />)

    // Expand
    await user.click(screen.getByLabelText('Toggle fallback history'))
    expect(screen.getByText('Verification Failed')).toBeInTheDocument()

    // Collapse
    await user.click(screen.getByLabelText('Toggle fallback history'))
    expect(screen.queryByText('Verification Failed')).not.toBeInTheDocument()
  })

  it('renders when _fallback_history exists but _is_fallback is false (history-only)', () => {
    const incident = {
      meta: {
        recommendation: { proposed_action: 'restart_service' },
        _is_fallback: false,
        _fallback_history: [
          { action: 'old_action', status: 'verification_failed', reason: 'Failed' },
        ],
      },
    }
    render(<FallbackHistory incident={incident} />)
    expect(screen.getByText('Fallback History')).toBeInTheDocument()
    expect(screen.queryByText('Using fallback action')).not.toBeInTheDocument()
  })
})
