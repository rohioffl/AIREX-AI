import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import SeverityBadge from '../components/common/SeverityBadge'

describe('SeverityBadge', () => {
  it('renders CRITICAL severity', () => {
    render(<SeverityBadge severity="CRITICAL" />)
    expect(screen.getByText('CRITICAL')).toBeInTheDocument()
  })

  it('renders all 4 severities', () => {
    const severities = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    severities.forEach((sev) => {
      const { unmount } = render(<SeverityBadge severity={sev} />)
      expect(screen.getByText(sev)).toBeInTheDocument()
      unmount()
    })
  })

  it('handles unknown severity gracefully', () => {
    render(<SeverityBadge severity="UNKNOWN" />)
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument()
  })
})
