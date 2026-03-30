import { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react'
import { login as apiLogin, logout as apiLogout, refreshToken as apiRefreshToken, googleLogin as apiGoogleLogin, platformAdminLogin as apiPlatformAdminLogin, platformAdminGoogleLogin as apiPlatformAdminGoogleLogin } from '../services/auth'
import { getRefreshToken, getValidAccessToken } from '../services/tokenStorage'
import { fetchAuthMe, getActiveTenantId, setActiveTenantId as persistActiveTenantId } from '../services/api'
import { deriveOrganizations } from '../utils/accessControl'

const AuthContext = createContext()

function parseTokenUser(t) {
  try {
    const payload = JSON.parse(atob(t.split('.')[1]))
    return {
      email: payload.sub,
      role: payload.role || 'operator',
      tenantId: payload.tenant_id,
      userId: payload.user_id,
    }
  } catch {
    return null
  }
}

function buildUser(parsed, me) {
  const meUser = me?.user || {}
  const activeTenant = me?.active_tenant || null
  return {
    email: meUser.email || parsed?.email || null,
    role: meUser.role || parsed?.role || 'operator',
    tenantId: activeTenant?.id || meUser.tenant_id || parsed?.tenantId || null,
    tenant_id: activeTenant?.id || meUser.tenant_id || parsed?.tenantId || null,
    homeTenantId: meUser.tenant_id || parsed?.tenantId || null,
    userId: meUser.id || parsed?.userId || null,
    user_id: meUser.id || parsed?.userId || null,
    displayName: meUser.display_name || parsed?.email || null,
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const t = getValidAccessToken()
    return t ? parseTokenUser(t) : null
  })
  const [token, setToken] = useState(() => getValidAccessToken() || null)
  const [loading, setLoading] = useState(() => !getValidAccessToken() && !!getRefreshToken())
  const [sessionContext, setSessionContext] = useState(null)

  const hydrateSession = useCallback(async (accessToken, tenantId = null) => {
    const parsed = accessToken ? parseTokenUser(accessToken) : null
    const resolvedTenantId = tenantId || getActiveTenantId() || parsed?.tenantId || null
    if (resolvedTenantId) {
      persistActiveTenantId(resolvedTenantId)
    }
    let me
    try {
      me = await fetchAuthMe(resolvedTenantId)
    } catch (error) {
      const detail = error?.response?.data?.detail
      if (detail === 'Tenant not found' && resolvedTenantId) {
        persistActiveTenantId(null)
        me = await fetchAuthMe(null)
      } else {
        throw error
      }
    }
    const nextUser = buildUser(parsed, me)
    setUser(nextUser)
    setSessionContext(me)
    if (me?.active_tenant?.id) {
      persistActiveTenantId(me.active_tenant.id)
    }
    return me
  }, [])

  const login = useCallback(async ({ email, password }) => {
    const res = await apiLogin({ email, password })
    setToken(res.access_token)
    await hydrateSession(res.access_token)
    return res
  }, [hydrateSession])

  const loginWithGoogle = useCallback(async (idToken) => {
    const res = await apiGoogleLogin(idToken)
    setToken(res.access_token)
    await hydrateSession(res.access_token)
    return res
  }, [hydrateSession])

  const loginAsPlatformAdmin = useCallback(async ({ email, password }) => {
    const res = await apiPlatformAdminLogin({ email, password })
    setToken(res.access_token)
    await hydrateSession(res.access_token)
    return res
  }, [hydrateSession])

  const loginWithGoogleAsAdmin = useCallback(async (idToken) => {
    const res = await apiPlatformAdminGoogleLogin(idToken)
    setToken(res.access_token)
    await hydrateSession(res.access_token)
    return res
  }, [hydrateSession])

  const logout = useCallback(() => {
    apiLogout()
    setUser(null)
    setToken(null)
    setSessionContext(null)
    persistActiveTenantId(null)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const res = await apiRefreshToken()
      setToken(res.access_token)
      await hydrateSession(res.access_token)
    } catch {
      logout()
    }
  }, [hydrateSession, logout])

  const switchTenant = useCallback(async (tenantId) => {
    persistActiveTenantId(tenantId)
    if (!token) return
    await hydrateSession(token, tenantId)
  }, [hydrateSession, token])

  useEffect(() => {
    if (token) {
      let cancelled = false

      async function ensureContext() {
        try {
          await hydrateSession(token)
        } catch {
          if (!cancelled) {
            logout()
          }
        } finally {
          if (!cancelled) {
            setLoading(false)
          }
        }
      }

      ensureContext()
      return () => {
        cancelled = true
      }
    }

    if (!getRefreshToken()) {
      setLoading(false)
      return
    }

    let cancelled = false

    async function bootstrapSession() {
      setLoading(true)
      try {
        const res = await apiRefreshToken()
        if (cancelled) return
        setToken(res.access_token)
        await hydrateSession(res.access_token)
      } catch {
        if (!cancelled) {
          logout()
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    bootstrapSession()

    return () => {
      cancelled = true
    }
  }, [hydrateSession, logout, token])

  useEffect(() => {
    const handleSessionExpired = () => {
      logout()
    }
    window.addEventListener('session-expired', handleSessionExpired)
    return () => window.removeEventListener('session-expired', handleSessionExpired)
  }, [logout])

  const value = useMemo(() => {
    const organizationMemberships = sessionContext?.organization_memberships || []
    const tenantMemberships = sessionContext?.tenant_memberships || []
    const organizations = deriveOrganizations(sessionContext)

    return {
      user,
      token,
      loading,
      login,
      loginWithGoogle,
      loginAsPlatformAdmin,
      loginWithGoogleAsAdmin,
      logout,
      refresh,
      switchTenant,
      isAuthenticated: !!token,
      sessionContext,
      organizationMemberships,
      tenantMemberships,
      organizations,
      tenants: sessionContext?.tenants || [],
      projects: sessionContext?.projects || [],
      activeOrganization: sessionContext?.active_organization || null,
      activeTenant: sessionContext?.active_tenant || null,
      activeTenantId: sessionContext?.active_tenant?.id || user?.tenantId || null,
    }
  }, [user, token, loading, login, loginWithGoogle, loginAsPlatformAdmin, loginWithGoogleAsAdmin, logout, refresh, switchTenant, sessionContext])

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components -- useAuth hook must co-locate with AuthProvider
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
