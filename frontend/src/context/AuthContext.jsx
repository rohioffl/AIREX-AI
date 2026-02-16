import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { login as apiLogin, logout as apiLogout, isAuthenticated, getToken, refreshToken } from '../services/auth'

const AuthContext = createContext()

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => getToken())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (isAuthenticated()) {
      try {
        const t = getToken()
        if (t) {
          const payload = JSON.parse(atob(t.split('.')[1]))
          setUser({
            email: payload.sub,
            role: payload.role || 'operator',
            tenantId: payload.tenant_id,
            userId: payload.user_id,
          })
          setToken(t)
        }
      } catch {
        apiLogout()
      }
    }
    setLoading(false)
  }, [])

  const login = useCallback(async ({ email, password }) => {
    const res = await apiLogin({ email, password })
    const payload = JSON.parse(atob(res.access_token.split('.')[1]))
    setUser({
      email: payload.sub,
      role: payload.role || 'operator',
      tenantId: payload.tenant_id,
      userId: payload.user_id,
    })
    setToken(res.access_token)
    if (payload.tenant_id) {
      localStorage.setItem('tenant_id', payload.tenant_id)
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
      const payload = JSON.parse(atob(res.access_token.split('.')[1]))
      setUser({
        email: payload.sub,
        role: payload.role || 'operator',
        tenantId: payload.tenant_id,
        userId: payload.user_id,
      })
      setToken(res.access_token)
    } catch {
      logout()
    }
  }, [logout])

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, refresh, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
