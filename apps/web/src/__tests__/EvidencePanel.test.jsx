import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import EvidencePanel from '../components/incident/EvidencePanel'

describe('EvidencePanel', () => {
  it('shows empty message when no evidence', () => {
    render(<EvidencePanel evidence={[]} />)
    expect(screen.getByText('No diagnostic artifacts collected.')).toBeInTheDocument()
  })

  it('shows empty message when evidence is null', () => {
    render(<EvidencePanel evidence={null} />)
    expect(screen.getByText('No diagnostic artifacts collected.')).toBeInTheDocument()
  })

  it('renders evidence items collapsed by default', () => {
    const evidence = [
      { id: '1', tool_name: 'cpu_check', raw_output: 'CPU at 95%', timestamp: '2026-01-01T00:00:00Z' },
    ]
    render(<EvidencePanel evidence={evidence} />)
    expect(screen.getByText('cpu_check')).toBeInTheDocument()
    // Collapsed view should not show the Raw Output panel yet
    expect(screen.queryByText('Raw Output')).not.toBeInTheDocument()
  })

  it('expands evidence on click', async () => {
    const evidence = [
      { id: '1', tool_name: 'cpu_check', raw_output: 'CPU at 95%', timestamp: '2026-01-01T00:00:00Z' },
    ]
    render(<EvidencePanel evidence={evidence} />)
    await userEvent.click(screen.getByText('cpu_check'))
    expect(screen.getByText('CPU at 95%')).toBeInTheDocument()
  })

  it('renders raw_output as text, never HTML', async () => {
    const evidence = [
      { id: '1', tool_name: 'test', raw_output: '<script>alert("xss")</script>', timestamp: '2026-01-01T00:00:00Z' },
    ]
    render(<EvidencePanel evidence={evidence} />)
    await userEvent.click(screen.getByText('test'))
    const pre = screen.getByText('<script>alert("xss")</script>')
    expect(pre.tagName).toBe('PRE')
  })
})
