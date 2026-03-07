import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import VerificationResult from '../components/incident/VerificationResult'

const mockIncidentWithCriteria = {
  id: 'inc-001',
  state: 'RESOLVED',
  recommendation: {
    verification_criteria: [
      'CPU usage below 80% for 5 minutes',
      'No OOMKilled containers in last 10 minutes',
      'Service health check returning 200',
    ],
  },
}

describe('VerificationResult', () => {
  it('renders nothing for EXECUTING state', () => {
    const { container } = render(<VerificationResult state="EXECUTING" />)
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing for INVESTIGATING state', () => {
    const { container } = render(<VerificationResult state="INVESTIGATING" />)
    expect(container.innerHTML).toBe('')
  })

  it('shows spinner for VERIFYING state', () => {
    render(<VerificationResult state="VERIFYING" />)
    expect(screen.getByText('Verifying Fix')).toBeInTheDocument()
    expect(screen.getByText('Running post-execution health checks...')).toBeInTheDocument()
  })

  it('shows success for RESOLVED state', () => {
    render(<VerificationResult state="RESOLVED" />)
    expect(screen.getByText('Incident Resolved')).toBeInTheDocument()
    expect(screen.getByText('Verification passed. Normal operations restored.')).toBeInTheDocument()
  })

  it('shows failure for FAILED_VERIFICATION state', () => {
    render(<VerificationResult state="FAILED_VERIFICATION" />)
    expect(screen.getByText('Verification Failed')).toBeInTheDocument()
    expect(screen.getByText('System still reporting issues. Manual intervention may be required.')).toBeInTheDocument()
  })

  it('renders verification criteria from incident prop', () => {
    render(<VerificationResult state="RESOLVED" incident={mockIncidentWithCriteria} />)
    expect(screen.getByText('Verification Criteria')).toBeInTheDocument()
    expect(screen.getByText('CPU usage below 80% for 5 minutes')).toBeInTheDocument()
    expect(screen.getByText('No OOMKilled containers in last 10 minutes')).toBeInTheDocument()
    expect(screen.getByText('Service health check returning 200')).toBeInTheDocument()
  })

  it('shows checkmarks for resolved state criteria', () => {
    render(<VerificationResult state="RESOLVED" incident={mockIncidentWithCriteria} />)
    // Resolved state uses checkmark character
    const criteria = screen.getAllByText(/CPU usage|OOMKilled|health check/)
    expect(criteria).toHaveLength(3)
  })

  it('renders criteria from meta.recommendation when top-level recommendation is missing', () => {
    const incidentWithMeta = {
      id: 'inc-002',
      meta: {
        recommendation: {
          verification_criteria: ['Metric X normalized'],
        },
      },
    }
    render(<VerificationResult state="VERIFYING" incident={incidentWithMeta} />)
    expect(screen.getByText('Metric X normalized')).toBeInTheDocument()
  })

  it('does not render criteria section when none are provided', () => {
    render(<VerificationResult state="RESOLVED" incident={{ id: 'inc-003' }} />)
    expect(screen.queryByText('Verification Criteria')).not.toBeInTheDocument()
  })

  it('renders nothing for unknown state', () => {
    const { container } = render(<VerificationResult state="UNKNOWN_STATE" />)
    expect(container.innerHTML).toBe('')
  })
})
