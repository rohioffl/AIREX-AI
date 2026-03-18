import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

/**
 * PrivateRoute - Protects routes that require authentication.
 * Redirects to /login if user is not authenticated.
 */
export default function PrivateRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    if (location.pathname === '/admin') {
      return <Navigate to="/admin/login" replace />
    }
    return <Navigate to="/login" replace />
  }

  return children
}
