import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle, Loader2, LogIn, ShieldAlert } from 'lucide-react'

import { useAuth } from '../context/AuthContext'
import { acceptInvitation, fetchInvitationInfo } from '../services/auth'
import { extractErrorMessage } from '../utils/errorHandler'

export default function AcceptInvitationPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { isAuthenticated, loading: authLoading, user, logout } = useAuth()
  const token = searchParams.get('token')

  const [invitation, setInvitation] = useState(null)
  const [loadingInvitation, setLoadingInvitation] = useState(true)
  const [accepting, setAccepting] = useState(false)
  const [error, setError] = useState(null)
  const acceptAttemptedRef = useRef(false)

  useEffect(() => {
    let cancelled = false

    async function loadInvitation() {
      if (!token) {
        setError('Invalid invitation link. Please use the link from your email.')
        setLoadingInvitation(false)
        return
      }

      setLoadingInvitation(true)
      setError(null)

      try {
        const data = await fetchInvitationInfo(token)
        if (cancelled) return

        if (data.mode === 'set_password') {
          navigate(`/set-password?token=${encodeURIComponent(token)}`, { replace: true })
          return
        }

        setInvitation(data)
      } catch (err) {
        if (!cancelled) {
          setError(extractErrorMessage(err) || 'Unable to load invitation details')
        }
      } finally {
        if (!cancelled) {
          setLoadingInvitation(false)
        }
      }
    }

    loadInvitation()

    return () => {
      cancelled = true
    }
  }, [navigate, token])

  useEffect(() => {
    let cancelled = false

    async function completeAcceptance() {
      if (!token || !invitation || authLoading || !isAuthenticated || !user?.email) {
        return
      }

      if (user.email.toLowerCase() !== invitation.email.toLowerCase()) {
        return
      }

      if (acceptAttemptedRef.current) {
        return
      }

      acceptAttemptedRef.current = true
      setAccepting(true)
      setError(null)

      try {
        await acceptInvitation(token)
        if (!cancelled) {
          navigate('/dashboard', { replace: true })
        }
      } catch (err) {
        if (!cancelled) {
          setError(extractErrorMessage(err) || 'Unable to accept invitation')
          setAccepting(false)
          acceptAttemptedRef.current = false
        }
      }
    }

    completeAcceptance()

    return () => {
      cancelled = true
    }
  }, [authLoading, invitation, isAuthenticated, navigate, token, user?.email])

  if (loadingInvitation || (isAuthenticated && authLoading) || accepting) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6" style={{ background: 'var(--bg-primary)' }}>
        <div className="glass rounded-2xl p-8 max-w-md w-full text-center space-y-4">
          <Loader2 className="mx-auto animate-spin" size={32} style={{ color: 'var(--neon-cyan)' }} />
          <div>
            <h1 className="text-xl font-semibold" style={{ color: 'var(--text-heading)' }}>
              {accepting ? 'Accepting invitation' : 'Loading invitation'}
            </h1>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              {accepting
                ? 'We are confirming your access and preparing your workspace.'
                : 'Checking the invitation details from your email link.'}
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6" style={{ background: 'var(--bg-primary)' }}>
      <div className="glass rounded-2xl p-8 max-w-lg w-full space-y-5">
        <div className="flex items-center gap-3">
          <CheckCircle size={24} style={{ color: 'var(--neon-cyan)' }} />
          <div>
            <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-heading)' }}>
              Accept organization invitation
            </h1>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Existing accounts can join a new organization without resetting their password.
            </p>
          </div>
        </div>

        {invitation ? (
          <div className="rounded-xl p-4 space-y-1" style={{ background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.24)' }}>
            <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Invited account
            </div>
            <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              {invitation.display_name} ({invitation.email})
            </div>
          </div>
        ) : null}

        {error ? (
          <div className="rounded-xl p-4 flex gap-3" style={{ background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.24)' }}>
            <ShieldAlert size={18} className="mt-0.5 text-red-500" />
            <div className="text-sm text-red-500">{error}</div>
          </div>
        ) : null}

        {!isAuthenticated ? (
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Sign in as <strong style={{ color: 'var(--text-primary)' }}>{invitation?.email || 'the invited user'}</strong> to accept this invitation.
            </p>
            <Link
              to={`/login?accept_invitation_token=${encodeURIComponent(token || '')}`}
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
              style={{ background: 'var(--gradient-primary)', color: '#fff' }}
            >
              <LogIn size={16} />
              Sign in to accept
            </Link>
          </div>
        ) : invitation && user?.email?.toLowerCase() !== invitation.email.toLowerCase() ? (
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              You are signed in as <strong style={{ color: 'var(--text-primary)' }}>{user?.email}</strong>, but this invitation is for <strong style={{ color: 'var(--text-primary)' }}>{invitation.email}</strong>.
            </p>
            <button
              type="button"
              onClick={() => {
                logout()
                navigate(`/login?accept_invitation_token=${encodeURIComponent(token || '')}`, { replace: true })
              }}
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold"
              style={{ background: 'var(--gradient-primary)', color: '#fff' }}
            >
              <LogIn size={16} />
              Sign in with the invited account
            </button>
          </div>
        ) : (
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            You are signed in as the invited user. Finishing access now.
          </p>
        )}
      </div>
    </div>
  )
}
