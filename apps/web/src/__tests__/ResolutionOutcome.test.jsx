import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ResolutionOutcome from '../components/incident/ResolutionOutcome'

vi.mock('../services/api', () => ({
  submitFeedback: vi.fn().mockResolvedValue({
    incident_id: 'inc-001',
    feedback_score: 4,
    feedback_note: 'Good fix',
  }),
}))

vi.mock('../utils/errorHandler', () => ({
  extractErrorMessage: vi.fn((e) => e?.message || 'Error'),
}))

const baseIncident = {
  id: 'inc-001',
  state: 'RESOLVED',
  resolution_type: 'operator',
  resolution_summary: 'Outcome: RESOLVED | Action: restart_service | Root cause: OOM',
  resolution_duration_seconds: 600,
  feedback_score: null,
  feedback_note: null,
  meta: {},
}

describe('ResolutionOutcome', () => {
  it('returns null for non-terminal states', () => {
    const incident = { ...baseIncident, state: 'INVESTIGATING' }
    const { container } = render(<ResolutionOutcome incident={incident} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders for RESOLVED state', () => {
    render(<ResolutionOutcome incident={baseIncident} />)
    expect(screen.getByText('Operator-Approved')).toBeInTheDocument()
  })

  it('renders for REJECTED state', () => {
    const incident = { ...baseIncident, state: 'REJECTED', resolution_type: 'rejected' }
    render(<ResolutionOutcome incident={incident} />)
    expect(screen.getByText('Rejected by Operator')).toBeInTheDocument()
  })

  it('shows auto resolution type', () => {
    const incident = { ...baseIncident, resolution_type: 'auto' }
    render(<ResolutionOutcome incident={incident} />)
    expect(screen.getByText('Autonomous Resolution')).toBeInTheDocument()
  })

  it('shows senior resolution type', () => {
    const incident = { ...baseIncident, resolution_type: 'senior' }
    render(<ResolutionOutcome incident={incident} />)
    expect(screen.getByText('Senior-Approved')).toBeInTheDocument()
  })

  it('shows failed resolution type', () => {
    const incident = { ...baseIncident, state: 'FAILED_EXECUTION', resolution_type: 'failed' }
    render(<ResolutionOutcome incident={incident} />)
    expect(screen.getByText('Resolution Failed')).toBeInTheDocument()
  })

  it('shows resolution summary', () => {
    render(<ResolutionOutcome incident={baseIncident} />)
    expect(screen.getByText('Resolution Summary')).toBeInTheDocument()
    expect(screen.getByText(/restart_service/)).toBeInTheDocument()
  })

  it('shows duration', () => {
    render(<ResolutionOutcome incident={baseIncident} />)
    expect(screen.getByText('10m')).toBeInTheDocument()
  })

  it('shows duration in hours', () => {
    const incident = { ...baseIncident, resolution_duration_seconds: 7200 }
    render(<ResolutionOutcome incident={incident} />)
    expect(screen.getByText('2h')).toBeInTheDocument()
  })

  it('shows feedback form when no feedback submitted', () => {
    render(<ResolutionOutcome incident={baseIncident} />)
    expect(screen.getByText('Rate This Resolution')).toBeInTheDocument()
    expect(screen.getByText('Submit Feedback')).toBeInTheDocument()
  })

  it('shows existing feedback when already submitted', () => {
    const incident = { ...baseIncident, feedback_score: 4, feedback_note: 'Good fix' }
    render(<ResolutionOutcome incident={incident} />)
    expect(screen.getByText('Operator Feedback')).toBeInTheDocument()
    expect(screen.getByText(/Great/)).toBeInTheDocument()
    expect(screen.getByText(/"Good fix"/)).toBeInTheDocument()
  })

  it('shows all score options', () => {
    render(<ResolutionOutcome incident={baseIncident} />)
    expect(screen.getByText('Harmful')).toBeInTheDocument()
    expect(screen.getByText('Ineffective')).toBeInTheDocument()
    expect(screen.getByText('Poor')).toBeInTheDocument()
    expect(screen.getByText('Fair')).toBeInTheDocument()
    expect(screen.getByText('Good')).toBeInTheDocument()
    expect(screen.getByText('Great')).toBeInTheDocument()
    expect(screen.getByText('Excellent')).toBeInTheDocument()
  })

  it('submit button disabled when no score selected', () => {
    render(<ResolutionOutcome incident={baseIncident} />)
    const btn = screen.getByText('Submit Feedback').closest('button')
    expect(btn).toBeDisabled()
  })

  it('handles missing resolution data gracefully', () => {
    const incident = {
      ...baseIncident,
      resolution_type: null,
      resolution_summary: null,
      resolution_duration_seconds: null,
    }
    render(<ResolutionOutcome incident={incident} />)
    // Should render with fallback config
    expect(screen.getByText('Rate This Resolution')).toBeInTheDocument()
  })

  it('renders for FAILED_VERIFICATION state', () => {
    const incident = { ...baseIncident, state: 'FAILED_VERIFICATION', resolution_type: 'failed' }
    render(<ResolutionOutcome incident={incident} />)
    expect(screen.getByText('Resolution Failed')).toBeInTheDocument()
  })
})
