import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import StateBadge from '../components/common/StateBadge'

describe('StateBadge', () => {
  it('renders the state text', () => {
    render(<StateBadge state="RECEIVED" />)
    expect(screen.getByText('RECEIVED')).toBeInTheDocument()
  })

  it('renders all states without crashing', () => {
    const states = [
      'RECEIVED', 'INVESTIGATING', 'RECOMMENDATION_READY', 'AWAITING_APPROVAL',
      'EXECUTING', 'VERIFYING', 'RESOLVED', 'FAILED_ANALYSIS',
      'FAILED_EXECUTION', 'FAILED_VERIFICATION', 'REJECTED',
    ]
    states.forEach((state) => {
      const { unmount } = render(<StateBadge state={state} />)
      expect(screen.getByText(state)).toBeInTheDocument()
      unmount()
    })
  })

  it('handles unknown state gracefully', () => {
    render(<StateBadge state="UNKNOWN_STATE" />)
    expect(screen.getByText('UNKNOWN_STATE')).toBeInTheDocument()
  })
})
