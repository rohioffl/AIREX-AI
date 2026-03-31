import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { canAccessRoute, normalizeRole } from '../../utils/accessControl'

/**
 * RequireRole - Protects routes that require specific roles.
 * 
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child components to render if authorized
 * @param {string|string[]} props.roles - Required role(s). Can be 'admin', 'operator', 'viewer', or array
 * @param {React.ReactNode} props.fallback - Optional fallback component (default: redirect to /dashboard)
 * @param {string} props.access - Optional named access policy
 */
export default function RequireRole({ children, roles, access = null, fallback = null }) {
  const auth = useAuth()
  const { user, loading, token, sessionContext } = auth
  const needsScopedSession = access === 'organizations_admin' || access === 'tenant_admin'

  if (loading || (needsScopedSession && token && !sessionContext)) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  // Normalize roles to array
  const requiredRoles = Array.isArray(roles) ? roles : [roles]
  const userRole = normalizeRole(user.role || 'operator')

  // Check if user has required role
  // Role hierarchy: admin > operator > viewer
  const roleHierarchy = {
    admin: ['admin', 'operator', 'viewer'],
    operator: ['operator', 'viewer'],
    viewer: ['viewer'],
  }

  const hasRoleAccess = requiredRoles.some(role => {
    const roleLower = normalizeRole(role)
    const allowedRoles = roleHierarchy[roleLower] || [roleLower]
    return allowedRoles.includes(userRole) || requiredRoles.includes(userRole)
  })
  const hasAccess = access ? canAccessRoute(auth, access) : hasRoleAccess

  if (!hasAccess) {
    if (fallback) {
      return fallback
    }
    // Redirect to dashboard with error message
    return <Navigate to="/dashboard" replace />
  }

  return children
}
