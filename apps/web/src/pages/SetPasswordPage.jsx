import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useToasts } from '../context/ToastContext'
import { Lock, CheckCircle, XCircle } from 'lucide-react'
import api from '../services/api'
import { setTokens } from '../services/tokenStorage'
import { acceptInvitationWithGoogle, fetchInvitationInfo } from '../services/auth'
import { extractErrorMessage } from '../utils/errorHandler'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '671714206735-8tdd47qt6el9m33fs4kjnocjqrcsq9dg.apps.googleusercontent.com'

export default function SetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { addToast } = useToasts()
  
  const token = searchParams.get('token')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingInvitation, setLoadingInvitation] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)
  const googleButtonRef = useRef(null)

  useEffect(() => {
    if (!token) {
      setError('Invalid invitation link. Please check your email for the correct link.')
    }
  }, [token])

  useEffect(() => {
    let cancelled = false

    async function validateMode() {
      if (!token) return

      setLoadingInvitation(true)
      try {
        const invitation = await fetchInvitationInfo(token)
        if (!cancelled && invitation.mode === 'accept_invitation') {
          navigate(`/accept-invitation?token=${encodeURIComponent(token)}`, { replace: true })
        }
      } catch (err) {
        if (!cancelled) {
          setError(extractErrorMessage(err) || 'Invalid invitation link')
        }
      } finally {
        if (!cancelled) {
          setLoadingInvitation(false)
        }
      }
    }

    validateMode()

    return () => {
      cancelled = true
    }
  }, [navigate, token])

  const handleGoogleResponse = useCallback(async (response) => {
    if (!token) {
      setError('Invalid invitation link')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const res = await acceptInvitationWithGoogle(token, response.credential)
      
      // Store tokens from response
      if (res.access_token) {
        setTokens({
          accessToken: res.access_token,
          refreshToken: res.refresh_token,
          expiresIn: res.expires_in || 3600,
        })
        // Force auth context refresh by reloading
        window.location.href = '/dashboard'
        return
      }
    } catch (err) {
      const errorMsg = extractErrorMessage(err) || err.response?.data?.detail || err.message || 'Google sign-in failed'
      setError(errorMsg)
      addToast({
        title: 'Error',
        message: errorMsg,
        severity: 'CRITICAL',
      })
    } finally {
      setLoading(false)
    }
  }, [token, addToast])

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !token) return

    const initGoogle = () => {
      if (!window.google?.accounts?.id) return
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleResponse,
      })
      if (googleButtonRef.current) {
        googleButtonRef.current.innerHTML = ''
        window.google.accounts.id.renderButton(googleButtonRef.current, {
          type: 'standard',
          theme: 'outline',
          size: 'large',
          text: 'signin_with',
          shape: 'pill',
          width: 340,
        })
      }
    }

    if (window.google?.accounts?.id) {
      initGoogle()
      return undefined
    }

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = initGoogle
    document.head.appendChild(script)

    return () => {
      if (document.head.contains(script)) document.head.removeChild(script)
    }
  }, [handleGoogleResponse, token])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    if (!token) {
      setError('Invalid invitation link')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long')
      return
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      const res = await api.post('/auth/set-password', {
        invitation_token: token,
        password: password,
      })
      
      // Store tokens from response
      if (res.data.access_token) {
        setTokens({
          accessToken: res.data.access_token,
          refreshToken: res.data.refresh_token,
          expiresIn: res.data.expires_in || 3600,
        })
        // Parse token to get user info and update auth context
        try {
          JSON.parse(atob(res.data.access_token.split('.')[1]))
          // Force auth context refresh by reloading
          window.location.href = '/dashboard'
          return
        } catch {
          // Fallback: navigate
          navigate('/dashboard')
        }
      }
      
      setSuccess(true)
      addToast({
        title: 'Success',
        message: 'Password set successfully! Redirecting...',
        severity: 'LOW',
      })
      
      // Redirect to dashboard after 2 seconds
      setTimeout(() => {
        navigate('/dashboard')
      }, 2000)
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to set password'
      setError(errorMsg)
      addToast({
        title: 'Error',
        message: errorMsg,
        severity: 'CRITICAL',
      })
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
        <div className="glass rounded-xl p-8 max-w-md w-full text-center">
          <CheckCircle size={48} className="mx-auto mb-4" style={{ color: 'var(--color-accent-green)' }} />
          <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--text-heading)' }}>
            Password Set Successfully!
          </h2>
          <p className="text-muted mb-4">
            Your account has been activated. Redirecting to dashboard...
          </p>
        </div>
      </div>
    )
  }

  if (loadingInvitation) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
        <div className="glass rounded-xl p-8 max-w-md w-full text-center">
          <p className="text-muted">Checking your invitation…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
      <div className="glass rounded-xl p-8 max-w-md w-full">
        <div className="flex items-center gap-3 mb-6">
          <Lock size={24} style={{ color: 'var(--neon-indigo)' }} />
          <h2 className="text-2xl font-bold" style={{ color: 'var(--text-heading)' }}>
            Set Your Password
          </h2>
        </div>
        
        {error && (
          <div className="mb-4 p-3 rounded-lg flex items-center gap-2" style={{ background: 'var(--glow-rose)', border: '1px solid rgba(244,63,94,0.3)' }}>
            <XCircle size={16} className="text-red-500" />
            <p className="text-sm text-red-500">{error}</p>
          </div>
        )}

        {GOOGLE_CLIENT_ID && (
          <div className="mb-6">
            <div className="relative mb-4">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border"></div>
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="px-2 bg-transparent text-muted">Or</span>
              </div>
            </div>
            <div className="flex justify-center" ref={googleButtonRef}></div>
            <p className="mt-3 text-xs text-muted text-center">
              Sign in with Google to accept your invitation without setting a password
            </p>
          </div>
        )}

        <div className="relative mb-4">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-border"></div>
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="px-2 bg-transparent text-muted">Or set a password</span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">New Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              placeholder="At least 8 characters"
              minLength={8}
              disabled={loading}
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1">Confirm Password</label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-border bg-input"
              placeholder="Confirm your password"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading || !token}
            className="w-full px-4 py-2 rounded-lg transition-all disabled:opacity-50"
            style={{ fontSize: 14, fontWeight: 600, color: '#fff', background: 'var(--gradient-primary)' }}
          >
            {loading ? 'Setting Password...' : 'Set Password'}
          </button>
        </form>

        <p className="mt-4 text-xs text-muted text-center">
          This link will expire in 7 days. If you need a new invitation, contact your administrator.
        </p>
      </div>
    </div>
  )
}
