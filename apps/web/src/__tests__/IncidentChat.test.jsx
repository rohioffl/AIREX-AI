import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import IncidentChat from '../components/incident/IncidentChat'

// Mock scrollIntoView (not available in jsdom)
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

// Mock API calls
vi.mock('../services/api', () => ({
  sendChatMessage: vi.fn(),
  fetchChatHistory: vi.fn().mockResolvedValue([]),
  clearChatHistory: vi.fn().mockResolvedValue({}),
}))

describe('IncidentChat', () => {
  it('renders the AI Chat header', () => {
    render(<IncidentChat incidentId="test-123" />)
    expect(screen.getByText('AI Chat')).toBeInTheDocument()
  })

  it('shows subtitle about asking questions', () => {
    render(<IncidentChat incidentId="test-123" />)
    expect(screen.getByText(/Ask questions about this incident/)).toBeInTheDocument()
  })

  it('is collapsed by default', () => {
    render(<IncidentChat incidentId="test-123" />)
    expect(screen.queryByPlaceholderText('Ask about this incident...')).not.toBeInTheDocument()
  })

  it('expands on header click and shows empty state', async () => {
    render(<IncidentChat incidentId="test-123" />)
    await userEvent.click(screen.getByText('AI Chat'))
    expect(screen.getByText('Ask about root cause, remediation steps, or historical patterns.')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Ask about this incident...')).toBeInTheDocument()
  })

  it('shows suggestion buttons in empty state', async () => {
    render(<IncidentChat incidentId="test-123" />)
    await userEvent.click(screen.getByText('AI Chat'))
    expect(screen.getByText('What caused this incident?')).toBeInTheDocument()
    expect(screen.getByText('Has this happened before?')).toBeInTheDocument()
    expect(screen.getByText('Is the recommended action safe?')).toBeInTheDocument()
  })

  it('fills input when suggestion button is clicked', async () => {
    render(<IncidentChat incidentId="test-123" />)
    await userEvent.click(screen.getByText('AI Chat'))
    await userEvent.click(screen.getByText('What caused this incident?'))
    const input = screen.getByPlaceholderText('Ask about this incident...')
    expect(input).toHaveValue('What caused this incident?')
  })

  it('disables send button when input is empty', async () => {
    render(<IncidentChat incidentId="test-123" />)
    await userEvent.click(screen.getByText('AI Chat'))
    // The send button is the one with disabled attribute when no input
    const buttons = screen.getAllByRole('button')
    const sendButton = buttons.find(b => b.disabled)
    expect(sendButton).toBeDefined()
    expect(sendButton).toBeDisabled()
  })

  it('collapses back when header is clicked again', async () => {
    render(<IncidentChat incidentId="test-123" />)
    await userEvent.click(screen.getByText('AI Chat'))
    expect(screen.getByPlaceholderText('Ask about this incident...')).toBeInTheDocument()

    await userEvent.click(screen.getByText('AI Chat'))
    expect(screen.queryByPlaceholderText('Ask about this incident...')).not.toBeInTheDocument()
  })
})
