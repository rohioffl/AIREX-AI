import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import ConfirmationModal from '../components/common/ConfirmationModal'

describe('ConfirmationModal', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <ConfirmationModal
        open={false}
        title="Test"
        message="Test message"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders title and message when open', () => {
    render(
      <ConfirmationModal
        open={true}
        title="Confirm Action"
        message="Are you sure?"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    )
    expect(screen.getByText('Confirm Action')).toBeInTheDocument()
    expect(screen.getByText('Are you sure?')).toBeInTheDocument()
  })

  it('calls onConfirm when Confirm is clicked', async () => {
    const onConfirm = vi.fn()
    render(
      <ConfirmationModal
        open={true}
        title="Test"
        message="msg"
        onConfirm={onConfirm}
        onCancel={() => {}}
      />
    )
    await userEvent.click(screen.getByText('Confirm'))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('calls onCancel when Cancel is clicked', async () => {
    const onCancel = vi.fn()
    render(
      <ConfirmationModal
        open={true}
        title="Test"
        message="msg"
        onConfirm={() => {}}
        onCancel={onCancel}
      />
    )
    await userEvent.click(screen.getByText('Cancel'))
    expect(onCancel).toHaveBeenCalledOnce()
  })
})
