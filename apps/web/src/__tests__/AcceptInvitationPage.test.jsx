import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockUseAuth = vi.fn()
const mockFetchInvitationInfo = vi.fn()
const mockAcceptInvitation = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}))

vi.mock('../services/auth', () => ({
  fetchInvitationInfo: (...args) => mockFetchInvitationInfo(...args),
  acceptInvitation: (...args) => mockAcceptInvitation(...args),
}))

import AcceptInvitationPage from '../pages/AcceptInvitationPage'

describe('AcceptInvitationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('prompts unauthenticated existing users to sign in before accepting', async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      loading: false,
      user: null,
      logout: vi.fn(),
    })
    mockFetchInvitationInfo.mockResolvedValue({
      email: 'rohit.pt@ankercloud.com',
      display_name: 'Rohit P T',
      mode: 'accept_invitation',
      expires_at: '2026-04-06T00:00:00Z',
    })

    render(
      <MemoryRouter initialEntries={['/accept-invitation?token=test-token']}>
        <Routes>
          <Route path="/accept-invitation" element={<AcceptInvitationPage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText('Accept organization invitation')).toBeInTheDocument()
    expect(screen.getByText(/sign in as/i)).toBeInTheDocument()

    const signInLink = screen.getByRole('link', { name: /sign in to accept/i })
    expect(signInLink.getAttribute('href')).toBe('/login?accept_invitation_token=test-token')
  })

  it('shows a clear mismatch message when the wrong account is signed in', async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      loading: false,
      user: { email: 'someone.else@example.com' },
      logout: vi.fn(),
    })
    mockFetchInvitationInfo.mockResolvedValue({
      email: 'rohit.pt@ankercloud.com',
      display_name: 'Rohit P T',
      mode: 'accept_invitation',
      expires_at: '2026-04-06T00:00:00Z',
    })

    render(
      <MemoryRouter initialEntries={['/accept-invitation?token=test-token']}>
        <Routes>
          <Route path="/accept-invitation" element={<AcceptInvitationPage />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText(/you are signed in as/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /sign in with the invited account/i })).toBeInTheDocument()
  })
})
