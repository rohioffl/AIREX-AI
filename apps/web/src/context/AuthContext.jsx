import { createContext, useContext, useState, useCallback, useMemo } from 'react'
import { login as apiLogin, logout as apiLogout, getToken, refreshToken } from '../services/auth'

const AuthContext = createContext()

const BYPASS_AUTH = import.meta.env.VITE_BYPASS_AUTH === 'true'

const DEV_USER = {
  email: 'dev@airex.local',
  role: 'operator',
  tenantId: '00000000-0000-0000-0000-000000000000',
  userId: 'dev-user',
  displayName: 'Dev User'
}

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

function getInitialUser() {
  if (BYPASS_AUTH) return DEV_USER
  const t = getToken()
  return t ? parseTokenUser(t) : null
}

function getInitialToken() {
  if (BYPASS_AUTH) return 'dev-token'
  return getToken() || null
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getInitialUser)
  const [token, setToken] = useState(getInitialToken)
  const loading = false

  const login = useCallback(async ({ email, password }) => {
    const res = await apiLogin({ email, password })
    const parsed = parseTokenUser(res.access_token)
    setUser(parsed)
    setToken(res.access_token)
    if (parsed?.tenantId) {
      localStorage.setItem('tenant_id', parsed.tenantId)
    }
    return res
  }, [])

  const logout = useCallback(() => {
    apiLogout()
    setUser(null)
    setToken(null)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const res = await refreshToken()
      const parsed = parseTokenUser(res.access_token)
      setUser(parsed)
      setToken(res.access_token)
    } catch {
      logout()
    }
  }, [logout])

  const isAuth = BYPASS_AUTH ? true : !!token

  const value = useMemo(() => ({
    user, token, loading, login, logout, refresh, isAuthenticated: isAuth
  }), [user, token, loading, login, logout, refresh, isAuth])

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
