import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import InvestigationTimeline from '../components/incident/InvestigationTimeline'

const mockSteps = [
  { probe_name: 'CPUHighInvestigation', status: 'completed', category: 'primary', anomaly_count: 2, duration_ms: 1234, total_steps: 4 },
  { probe_name: 'Site24x7Monitor', status: 'completed', category: 'monitoring', anomaly_count: 0, duration_ms: 567, total_steps: 4 },
  { probe_name: 'ChangeDetection', status: 'started', category: 'change', anomaly_count: 0, duration_ms: 0, total_steps: 4 },
  { probe_name: 'LogAnalysis', status: 'started', category: 'log_analysis', anomaly_count: 0, duration_ms: 0, total_steps: 4 },
]

describe('InvestigationTimeline', () => {
  it('returns null when probeSteps is empty', () => {
    const { container } = render(<InvestigationTimeline probeSteps={[]} />)
    expect(container.innerHTML).toBe('')
  })

  it('returns null when probeSteps is null', () => {
    const { container } = render(<InvestigationTimeline probeSteps={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders the investigation progress heading', () => {
    render(<InvestigationTimeline probeSteps={mockSteps} />)
    expect(screen.getByText('Investigation Progress')).toBeInTheDocument()
  })

  it('shows probe count in progress text', () => {
    render(<InvestigationTimeline probeSteps={mockSteps} />)
    // Text is split: "2/4 probes" + " • anomalies detected" in same <p>
    expect(screen.getByText(/2\/4 probes/)).toBeInTheDocument()
  })

  it('renders all probe names', () => {
    render(<InvestigationTimeline probeSteps={mockSteps} />)
    expect(screen.getByText('CPUHighInvestigation')).toBeInTheDocument()
    expect(screen.getByText('Site24x7Monitor')).toBeInTheDocument()
    expect(screen.getByText('ChangeDetection')).toBeInTheDocument()
    expect(screen.getByText('LogAnalysis')).toBeInTheDocument()
  })

  it('shows category badges for probes', () => {
    render(<InvestigationTimeline probeSteps={mockSteps} />)
    expect(screen.getByText('primary')).toBeInTheDocument()
    expect(screen.getByText('monitoring')).toBeInTheDocument()
    expect(screen.getByText('change')).toBeInTheDocument()
  })

  it('shows anomaly count when anomalies are detected', () => {
    render(<InvestigationTimeline probeSteps={mockSteps} />)
    // Multiple matches: header + per-probe. Use getAllByText.
    const matches = screen.getAllByText(/anomal(y|ies) detected/i)
    expect(matches.length).toBeGreaterThanOrEqual(1)
  })

  it('shows anomalies detected indicator in header', () => {
    render(<InvestigationTimeline probeSteps={mockSteps} />)
    // The <p> tag contains both "2/4 probes" and "anomalies detected"
    const header = screen.getByText(/2\/4 probes/)
    expect(header.textContent).toContain('anomalies detected')
  })

  it('shows duration for completed probes', () => {
    render(<InvestigationTimeline probeSteps={mockSteps} />)
    expect(screen.getByText('1.2s')).toBeInTheDocument()
    expect(screen.getByText('567ms')).toBeInTheDocument()
  })

  it('shows status labels', () => {
    render(<InvestigationTimeline probeSteps={mockSteps} />)
    expect(screen.getAllByText('Done')).toHaveLength(2)
    expect(screen.getAllByText('Running')).toHaveLength(2)
  })

  it('collapses and expands on toggle click', async () => {
    render(<InvestigationTimeline probeSteps={mockSteps} />)
    // Initially expanded
    expect(screen.getByText('CPUHighInvestigation')).toBeInTheDocument()

    // Click to collapse
    await userEvent.click(screen.getByText('Investigation Progress'))
    expect(screen.queryByText('CPUHighInvestigation')).not.toBeInTheDocument()

    // Click to expand again
    await userEvent.click(screen.getByText('Investigation Progress'))
    expect(screen.getByText('CPUHighInvestigation')).toBeInTheDocument()
  })

  it('shows completed status when all probes are done', () => {
    const allDone = [
      { probe_name: 'Probe1', status: 'completed', category: 'primary', anomaly_count: 0, duration_ms: 100, total_steps: 2 },
      { probe_name: 'Probe2', status: 'completed', category: 'secondary', anomaly_count: 0, duration_ms: 200, total_steps: 2 },
    ]
    render(<InvestigationTimeline probeSteps={allDone} />)
    expect(screen.getByText('2 probes completed')).toBeInTheDocument()
  })
})
