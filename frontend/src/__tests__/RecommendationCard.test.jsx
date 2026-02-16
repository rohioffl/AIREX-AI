import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import RecommendationCard from '../components/incident/RecommendationCard'

const mockRecommendation = {
  root_cause: 'High CPU from runaway process',
  proposed_action: 'restart_service',
  risk_level: 'MED',
  confidence: 0.85,
}

describe('RecommendationCard', () => {
  it('shows shimmer for early states with no recommendation', () => {
    render(<RecommendationCard recommendation={null} state="INVESTIGATING" />)
    expect(screen.getByText('Analysis in Progress...')).toBeInTheDocument()
  })

  it('renders recommendation when state is AWAITING_APPROVAL', () => {
    render(<RecommendationCard recommendation={mockRecommendation} state="AWAITING_APPROVAL" />)
    expect(screen.getByText('High CPU from runaway process')).toBeInTheDocument()
    expect(screen.getByText('restart_service')).toBeInTheDocument()
    expect(screen.getByText(/85\.0%/)).toBeInTheDocument()
  })

  it('shows recommendation for RESOLVED state', () => {
    render(<RecommendationCard recommendation={mockRecommendation} state="RESOLVED" />)
    expect(screen.getByText('restart_service')).toBeInTheDocument()
  })

  it('shows recommendation for FAILED states', () => {
    render(<RecommendationCard recommendation={mockRecommendation} state="FAILED_EXECUTION" />)
    expect(screen.getByText('restart_service')).toBeInTheDocument()
  })

  it('shows warning icon for HIGH risk', () => {
    const highRisk = { ...mockRecommendation, risk_level: 'HIGH' }
    render(<RecommendationCard recommendation={highRisk} state="AWAITING_APPROVAL" />)
    expect(screen.getByText('HIGH RISK')).toBeInTheDocument()
  })

  it('shows loading skeleton when recommendation is null in valid state', () => {
    const { container } = render(<RecommendationCard recommendation={null} state="AWAITING_APPROVAL" />)
    expect(container.querySelector('.shimmer')).toBeInTheDocument()
  })
})
