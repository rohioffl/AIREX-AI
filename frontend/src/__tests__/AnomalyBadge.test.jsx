import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import AnomalyBadge from '../components/incident/AnomalyBadge'

const criticalAnomalies = [
  { metric_name: 'cpu_percent', value: 98.5, threshold: 80, severity: 'critical', description: 'CPU usage critical' },
  { metric_name: 'load_avg', value: 12.3, threshold: 4, severity: 'warning', description: 'High load average' },
]

const warningOnly = [
  { metric_name: 'memory_percent', value: 75, threshold: 70, severity: 'warning', description: 'Memory elevated' },
]

const infoOnly = [
  { metric_name: 'disk_io', value: 50, threshold: 100, severity: 'info', description: 'Disk IO normal' },
]

describe('AnomalyBadge', () => {
  it('returns null when anomalies is null', () => {
    const { container } = render(<AnomalyBadge anomalies={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('returns null when anomalies is empty array', () => {
    const { container } = render(<AnomalyBadge anomalies={[]} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders anomaly count text with correct plural', () => {
    render(<AnomalyBadge anomalies={criticalAnomalies} />)
    expect(screen.getByText('2 Anomalies Detected')).toBeInTheDocument()
  })

  it('renders singular text for single anomaly', () => {
    render(<AnomalyBadge anomalies={warningOnly} />)
    expect(screen.getByText('1 Anomaly Detected')).toBeInTheDocument()
  })

  it('renders anomaly description badges', () => {
    render(<AnomalyBadge anomalies={criticalAnomalies} />)
    expect(screen.getByText('CPU usage critical')).toBeInTheDocument()
    expect(screen.getByText('High load average')).toBeInTheDocument()
  })

  it('shows tooltip with metric details', () => {
    render(<AnomalyBadge anomalies={criticalAnomalies} />)
    const badge = screen.getByText('CPU usage critical')
    expect(badge).toHaveAttribute('title', 'cpu_percent: 98.5 (threshold: 80)')
  })

  it('falls back to metric_name when description is missing', () => {
    const noDesc = [{ metric_name: 'swap_usage', value: 80, threshold: 50, severity: 'warning' }]
    render(<AnomalyBadge anomalies={noDesc} />)
    expect(screen.getByText('swap_usage')).toBeInTheDocument()
  })

  it('shows +N more when more than 6 anomalies', () => {
    const many = Array.from({ length: 8 }, (_, i) => ({
      metric_name: `metric_${i}`,
      value: i * 10,
      threshold: 50,
      severity: 'warning',
      description: `Anomaly ${i}`,
    }))
    render(<AnomalyBadge anomalies={many} />)
    expect(screen.getByText('+2 more')).toBeInTheDocument()
  })

  it('uses critical styling when any anomaly is critical', () => {
    render(<AnomalyBadge anomalies={criticalAnomalies} />)
    const header = screen.getByText('2 Anomalies Detected')
    // Critical color is #f43f5e
    expect(header).toHaveStyle({ color: '#f43f5e' })
  })

  it('uses warning styling when highest severity is warning', () => {
    render(<AnomalyBadge anomalies={warningOnly} />)
    const header = screen.getByText('1 Anomaly Detected')
    expect(header).toHaveStyle({ color: '#f59e0b' })
  })

  it('uses info styling when all anomalies are info', () => {
    render(<AnomalyBadge anomalies={infoOnly} />)
    const header = screen.getByText('1 Anomaly Detected')
    expect(header).toHaveStyle({ color: '#06b6d4' })
  })
})
