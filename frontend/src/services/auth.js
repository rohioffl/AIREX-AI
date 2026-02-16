/**
 * Authentication service — register, login, refresh, logout.
 */

import api from './api'

export async function register({ email, password, displayName, tenantId }) {
  const res = await api.post('/auth/register', {
    email,
    password,
    display_name: displayName,
    tenant_id: tenantId || undefined,
  })
  return res.data
}

export async function login({ email, password }) {
  const res = await api.post('/auth/login', { email, password })
  const { access_token, refresh_token, expires_in } = res.data

  localStorage.setItem('airex-token', access_token)
  if (refresh_token) {
    localStorage.setItem('airex-refresh-token', refresh_token)
  }
  localStorage.setItem('airex-token-expiry', String(Date.now() + expires_in * 1000))

  return res.data
}

export async function refreshToken() {
  const rt = localStorage.getItem('airex-refresh-token')
  if (!rt) throw new Error('No refresh token')

  const res = await api.post('/auth/refresh', { refresh_token: rt })
  const { access_token, expires_in } = res.data

  localStorage.setItem('airex-token', access_token)
  localStorage.setItem('airex-token-expiry', String(Date.now() + expires_in * 1000))

  return res.data
}

export function logout() {
  localStorage.removeItem('airex-token')
  localStorage.removeItem('airex-refresh-token')
  localStorage.removeItem('airex-token-expiry')
}

export function isAuthenticated() {
  const token = localStorage.getItem('airex-token')
  const expiry = localStorage.getItem('airex-token-expiry')
  if (!token) return false
  if (expiry && Date.now() > Number(expiry)) return false
  return true
}

export function getToken() {
  return localStorage.getItem('airex-token')
}
