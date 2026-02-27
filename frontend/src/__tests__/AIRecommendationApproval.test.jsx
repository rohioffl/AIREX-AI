import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import AIRecommendationApproval from '../components/incident/AIRecommendationApproval'

// Mock API + modules
vi.mock('../services/api', () => ({
  approveIncident: vi.fn().mockResolvedValue({}),
}))

vi.mock('../utils/errorHandler', () => ({
  extractErrorMessage: vi.fn((e) => e?.message || 'Error'),
}))

const mockIncidentBase = {
  id: 'inc-001',
  state: 'AWAITING_APPROVAL',
  meta: {},
}

const mockRecommendation = {
  root_cause: 'High CPU from runaway process',
  proposed_action: 'restart_service',
  risk_level: 'MED',
  confidence: 0.85,
  summary: 'Restart the runaway service to restore CPU',
  rationale: 'Process consuming 95% CPU for 30 minutes',
  blast_radius: 'Single service',
  root_cause_category: 'resource_exhaustion',
  contributing_factors: ['Memory leak', 'No resource limits'],
  alternatives: [
    { action: 'scale_instances', rationale: 'Add capacity', confidence: 0.6, risk_level: 'LOW' },
  ],
  verification_criteria: ['CPU below 80%', 'Service healthy'],
  reasoning_chain: [],
  evidence_annotations: {},
}

describe('AIRecommendationApproval', () => {
  it('returns null when no recommendation, ragContext, or approval state', () => {
    const incident = { ...mockIncidentBase, state: 'INVESTIGATING', recommendation: null }
    const { container } = render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders when state is AWAITING_APPROVAL even without recommendation', () => {
    const incident = { ...mockIncidentBase, recommendation: null }
    render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(screen.getByText('AI Recommendation & Approval')).toBeInTheDocument()
    expect(screen.getByText('AI Recommendation Pending')).toBeInTheDocument()
  })

  it('renders primary recommendation details', () => {
    const incident = { ...mockIncidentBase, recommendation: mockRecommendation }
    render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(screen.getByText('Primary Recommendation')).toBeInTheDocument()
    expect(screen.getByText('restart_service')).toBeInTheDocument()
    expect(screen.getByText('85% confidence')).toBeInTheDocument()
    expect(screen.getByText(/High CPU from runaway process/)).toBeInTheDocument()
  })

  it('shows risk level badge', () => {
    const incident = { ...mockIncidentBase, recommendation: mockRecommendation }
    render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(screen.getByText('MED RISK')).toBeInTheDocument()
  })

  it('shows confidence percentage', () => {
    const incident = { ...mockIncidentBase, recommendation: mockRecommendation }
    render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(screen.getByText('CONFIDENCE: 85.0%')).toBeInTheDocument()
  })

  it('shows contributing factors', () => {
    const incident = { ...mockIncidentBase, recommendation: mockRecommendation }
    render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(screen.getByText(/Memory leak/)).toBeInTheDocument()
    expect(screen.getByText(/No resource limits/)).toBeInTheDocument()
  })

  it('shows rationale section', () => {
    const incident = { ...mockIncidentBase, recommendation: mockRecommendation }
    render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(screen.getByText('Rationale:')).toBeInTheDocument()
    expect(screen.getByText('Process consuming 95% CPU for 30 minutes')).toBeInTheDocument()
  })

  it('shows blast radius', () => {
    const incident = { ...mockIncidentBase, recommendation: mockRecommendation }
    render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(screen.getByText('Single service')).toBeInTheDocument()
  })

  it('renders alternative recommendations', () => {
    const incident = { ...mockIncidentBase, recommendation: mockRecommendation }
    render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(screen.getByText('Alternative Options (AI-generated)')).toBeInTheDocument()
    expect(screen.getByText('scale_instances')).toBeInTheDocument()
    expect(screen.getByText('60% confidence')).toBeInTheDocument()
    expect(screen.getByText('Add capacity')).toBeInTheDocument()
  })

  it('shows Approve & Execute button in AWAITING_APPROVAL state', () => {
    const incident = { ...mockIncidentBase, recommendation: mockRecommendation }
    render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(screen.getByText('Approve & Execute')).toBeInTheDocument()
  })

  it('hides Approve button when state is not AWAITING_APPROVAL', () => {
    const incident = { ...mockIncidentBase, state: 'RESOLVED', recommendation: mockRecommendation }
    render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(screen.queryByText('Approve & Execute')).not.toBeInTheDocument()
  })

  it('shows HIGH RISK badge for high risk recommendations', () => {
    const highRiskRec = { ...mockRecommendation, risk_level: 'HIGH' }
    const incident = { ...mockIncidentBase, recommendation: highRiskRec }
    render(<AIRecommendationApproval incident={incident} ragContext={null} />)
    expect(screen.getByText('HIGH RISK')).toBeInTheDocument()
  })
})
