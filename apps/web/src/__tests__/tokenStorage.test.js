import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import {
  clearAccessToken,
  clearTokens,
  getRefreshToken,
  getToken,
  getTokenExpiry,
  getValidAccessToken,
  hasValidAccessToken,
  setTokens,
} from '../services/tokenStorage'

describe('tokenStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('stores access token, refresh token, and expiry', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-09T00:00:00Z'))

    setTokens({ accessToken: 'access', refreshToken: 'refresh', expiresIn: 60 })

    expect(getToken()).toBe('access')
    expect(getRefreshToken()).toBe('refresh')
    expect(getTokenExpiry()).toBe(Date.parse('2026-03-09T00:01:00Z'))
  })

  it('treats expired access token as invalid', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-09T00:00:00Z'))

    setTokens({ accessToken: 'access', expiresIn: 60 })
    vi.setSystemTime(new Date('2026-03-09T00:02:00Z'))

    expect(hasValidAccessToken()).toBe(false)
    expect(getValidAccessToken()).toBeNull()
  })

  it('honors expiry buffer for soon-to-expire tokens', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-09T00:00:00Z'))

    setTokens({ accessToken: 'access', expiresIn: 3 })

    expect(hasValidAccessToken()).toBe(true)
    expect(hasValidAccessToken(5000)).toBe(false)
  })

  it('clears only access token data when requested', () => {
    setTokens({ accessToken: 'access', refreshToken: 'refresh', expiresIn: 60 })

    clearAccessToken()

    expect(getToken()).toBeNull()
    expect(getTokenExpiry()).toBeNull()
    expect(getRefreshToken()).toBe('refresh')
  })

  it('clears all token data on logout', () => {
    setTokens({ accessToken: 'access', refreshToken: 'refresh', expiresIn: 60 })

    clearTokens()

    expect(getToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
    expect(getTokenExpiry()).toBeNull()
  })
})
