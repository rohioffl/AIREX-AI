/**
 * Authentication service — register, login, refresh, logout.
 */

import api from './api'
import {
  clearTokens,
  getToken as readAccessToken,
  hasValidAccessToken,
  setTokens,
} from './tokenStorage'

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

  setTokens({ accessToken: access_token, refreshToken: refresh_token, expiresIn: expires_in })

  return res.data
}

export async function refreshToken() {
  const rt = localStorage.getItem('airex-refresh-token')
  if (!rt) throw new Error('No refresh token')

  const res = await api.post('/auth/refresh', { refresh_token: rt })
  const { access_token, expires_in } = res.data

  setTokens({ accessToken: access_token, expiresIn: expires_in })

  return res.data
}

export function logout() {
  clearTokens()
}

export async function googleLogin(idToken) {
  const res = await api.post('/auth/google', { id_token: idToken })
  const { access_token, refresh_token, expires_in } = res.data

  setTokens({ accessToken: access_token, refreshToken: refresh_token, expiresIn: expires_in })

  return res.data
}

export async function acceptInvitationWithGoogle(invitationToken, idToken) {
  const res = await api.post('/auth/accept-invitation-with-google', {
    invitation_token: invitationToken,
    id_token: idToken,
  })
  const { access_token, refresh_token, expires_in } = res.data

  setTokens({ accessToken: access_token, refreshToken: refresh_token, expiresIn: expires_in })

  return res.data
}

export function isAuthenticated() {
  return hasValidAccessToken()
}

export function getToken() {
  return readAccessToken()
}
