import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useToasts } from '../context/ToastContext'
import { Lock, CheckCircle, XCircle } from 'lucide-react'
import api from '../services/api'
import { setTokens } from '../services/tokenStorage'

export default function SetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { login } = useAuth()
  const { addToast } = useToasts()
  
  const token = searchParams.get('token')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    if (!token) {
      setError('Invalid invitation link. Please check your email for the correct link.')
    }
  }, [token])

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
          const payload = JSON.parse(atob(res.data.access_token.split('.')[1]))
          // Force auth context refresh by reloading
          window.location.href = '/dashboard'
          return
        } catch (e) {
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
          <CheckCircle size={48} className="mx-auto mb-4" style={{ color: '#10b981' }} />
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

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
      <div className="glass rounded-xl p-8 max-w-md w-full">
        <div className="flex items-center gap-3 mb-6">
          <Lock size={24} style={{ color: '#6366f1' }} />
          <h2 className="text-2xl font-bold" style={{ color: 'var(--text-heading)' }}>
            Set Your Password
          </h2>
        </div>
        
        {error && (
          <div className="mb-4 p-3 rounded-lg flex items-center gap-2" style={{ background: 'rgba(244,63,94,0.1)', border: '1px solid rgba(244,63,94,0.3)' }}>
            <XCircle size={16} className="text-red-500" />
            <p className="text-sm text-red-500">{error}</p>
          </div>
        )}

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
            />
          </div>

          <button
            type="submit"
            disabled={loading || !token}
            className="w-full px-4 py-2 rounded-lg transition-all disabled:opacity-50"
            style={{ fontSize: 14, fontWeight: 600, color: '#fff', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
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
