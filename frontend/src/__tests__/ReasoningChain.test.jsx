import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import ReasoningChain from '../components/incident/ReasoningChain'

const mockChain = [
  { step: 1, description: 'Analyzed CPU utilization metrics', evidence_used: 'cpu_check output' },
  { step: 2, description: 'Correlated with memory pressure', evidence_used: 'mem_check output' },
  { step: 3, description: 'Identified runaway Java process' },
]

const mockCriteria = [
  'CPU usage below 80% for 5 minutes',
  'No OOMKilled containers',
  'Service health check passing',
]

describe('ReasoningChain', () => {
  it('returns null when both props are empty', () => {
    const { container } = render(<ReasoningChain reasoningChain={[]} verificationCriteria={[]} />)
    expect(container.innerHTML).toBe('')
  })

  it('returns null when both props are null', () => {
    const { container } = render(<ReasoningChain reasoningChain={null} verificationCriteria={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders the reasoning chain header with step count', () => {
    render(<ReasoningChain reasoningChain={mockChain} verificationCriteria={[]} />)
    expect(screen.getByText('AI Reasoning Chain (3 steps)')).toBeInTheDocument()
  })

  it('shows reasoning steps after expanding', async () => {
    render(<ReasoningChain reasoningChain={mockChain} verificationCriteria={[]} />)
    // Initially collapsed
    expect(screen.queryByText('Analyzed CPU utilization metrics')).not.toBeInTheDocument()

    // Click to expand
    await userEvent.click(screen.getByText('AI Reasoning Chain (3 steps)'))
    expect(screen.getByText('Analyzed CPU utilization metrics')).toBeInTheDocument()
    expect(screen.getByText('Correlated with memory pressure')).toBeInTheDocument()
    expect(screen.getByText('Identified runaway Java process')).toBeInTheDocument()
  })

  it('shows evidence_used when present', async () => {
    render(<ReasoningChain reasoningChain={mockChain} verificationCriteria={[]} />)
    await userEvent.click(screen.getByText('AI Reasoning Chain (3 steps)'))
    expect(screen.getByText('Evidence: cpu_check output')).toBeInTheDocument()
    expect(screen.getByText('Evidence: mem_check output')).toBeInTheDocument()
  })

  it('renders verification criteria after expanding', async () => {
    render(<ReasoningChain reasoningChain={[]} verificationCriteria={mockCriteria} />)
    await userEvent.click(screen.getByText(/AI Reasoning Chain/))
    expect(screen.getByText('Verification Criteria')).toBeInTheDocument()
    expect(screen.getByText('CPU usage below 80% for 5 minutes')).toBeInTheDocument()
    expect(screen.getByText('No OOMKilled containers')).toBeInTheDocument()
    expect(screen.getByText('Service health check passing')).toBeInTheDocument()
  })

  it('renders both reasoning chain and verification criteria together', async () => {
    render(<ReasoningChain reasoningChain={mockChain} verificationCriteria={mockCriteria} />)
    await userEvent.click(screen.getByText('AI Reasoning Chain (3 steps)'))
    // Reasoning steps
    expect(screen.getByText('Analyzed CPU utilization metrics')).toBeInTheDocument()
    // Verification criteria
    expect(screen.getByText('Verification Criteria')).toBeInTheDocument()
    expect(screen.getByText('CPU usage below 80% for 5 minutes')).toBeInTheDocument()
  })

  it('shows step numbers in reasoning chain', async () => {
    render(<ReasoningChain reasoningChain={mockChain} verificationCriteria={[]} />)
    await userEvent.click(screen.getByText('AI Reasoning Chain (3 steps)'))
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })
})
