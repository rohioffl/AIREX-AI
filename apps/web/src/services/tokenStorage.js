const ACCESS_TOKEN_KEY = 'airex-token'
const REFRESH_TOKEN_KEY = 'airex-refresh-token'
const TOKEN_EXPIRY_KEY = 'airex-token-expiry'

export function getToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function getTokenExpiry() {
  const raw = localStorage.getItem(TOKEN_EXPIRY_KEY)
  const expiry = raw ? Number(raw) : null
  return Number.isFinite(expiry) ? expiry : null
}

export function setTokens({ accessToken, refreshToken, expiresIn }) {
  if (accessToken) {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  }

  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  }

  if (typeof expiresIn === 'number') {
    localStorage.setItem(TOKEN_EXPIRY_KEY, String(Date.now() + expiresIn * 1000))
  }
}

export function clearAccessToken() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(TOKEN_EXPIRY_KEY)
}

export function clearTokens() {
  clearAccessToken()
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function hasValidAccessToken(bufferMs = 0) {
  const token = getToken()
  if (!token) return false

  const expiry = getTokenExpiry()
  if (expiry && Date.now() + bufferMs >= expiry) {
    return false
  }

  return true
}

export function getValidAccessToken(bufferMs = 0) {
  return hasValidAccessToken(bufferMs) ? getToken() : null
}
