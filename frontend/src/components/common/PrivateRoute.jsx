import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

/**
 * PrivateRoute - Protects routes that require authentication.
 * Redirects to /login if user is not authenticated.
 * 
 * TEMPORARILY DISABLED: Login bypassed for development/testing
 */
export default function PrivateRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()

  // TEMPORARILY DISABLED: Always allow access
  // TODO: Re-enable authentication before production
  const BYPASS_AUTH = true

  if (BYPASS_AUTH) {
    return children
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return children
}
