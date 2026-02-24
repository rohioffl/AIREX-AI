import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import VerificationResult from '../components/incident/VerificationResult'

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
  })

  it('shows success for RESOLVED state', () => {
    render(<VerificationResult state="RESOLVED" />)
    expect(screen.getByText('Incident Resolved')).toBeInTheDocument()
  })

  it('shows failure for FAILED_VERIFICATION state', () => {
    render(<VerificationResult state="FAILED_VERIFICATION" />)
    expect(screen.getByText('Verification Failed')).toBeInTheDocument()
  })

})
