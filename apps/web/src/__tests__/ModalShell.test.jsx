import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import ModalShell from '../components/common/ModalShell'

describe('ModalShell', () => {
  it('renders an accessible dialog and closes on escape and overlay click', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    render(
      <ModalShell onClose={onClose} title="Workspace Dialog">
        <button type="button">Inner Action</button>
      </ModalShell>
    )

    expect(screen.getByRole('dialog', { name: 'Workspace Dialog' })).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Workspace Dialog' })).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)

    const overlay = screen.getByRole('dialog', { name: 'Workspace Dialog' }).parentElement?.firstChild
    await user.click(overlay)
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
