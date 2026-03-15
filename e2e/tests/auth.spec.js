/**
 * E2E tests for AIREX authentication flows.
 *
 * Prerequisites:
 *   docker-compose up -d (all services running)
 *   Frontend at localhost:5173, Backend at localhost:8000
 *
 * Covers: login success, login failure, logout, session persistence.
 */

import { test, expect } from '@playwright/test'

const API = process.env.API_URL || 'http://localhost:8000'

let testEmail = ''
let testToken = ''

test.describe('Authentication Flow', () => {
  test.beforeAll(async ({ request }) => {
    // Register a dedicated e2e auth user
    testEmail = `e2e-auth-${Date.now()}@test.airex.dev`
    await request.post(`${API}/api/v1/auth/register`, {
      data: { email: testEmail, password: 'AuthTest1234!', display_name: 'E2E Auth User' },
    })

    const res = await request.post(`${API}/api/v1/auth/login`, {
      data: { email: testEmail, password: 'AuthTest1234!' },
    })
    const body = await res.json()
    testToken = body.access_token
  })

  test('login page renders correctly', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('input[type="email"], input[name="email"]').first()).toBeVisible()
    await expect(page.locator('input[type="password"]').first()).toBeVisible()
    await expect(page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")').first()).toBeVisible()
  })

  test('login with invalid credentials shows error', async ({ page }) => {
    await page.goto('/login')

    await page.locator('input[type="email"], input[name="email"]').first().fill('wrong@example.com')
    await page.locator('input[type="password"]').first().fill('wrongpassword')
    await page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")').first().click()

    // Should show an error message — not redirect
    await page.waitForTimeout(2000)
    await expect(page).toHaveURL(/\/login/)

    // Error message should be visible
    const errorLocator = page.locator('[role="alert"], .error, [class*="error"], [class*="Error"]')
    await expect(errorLocator.first()).toBeVisible({ timeout: 5000 })
  })

  test('login with valid credentials redirects to dashboard', async ({ page }) => {
    await page.goto('/login')

    await page.locator('input[type="email"], input[name="email"]').first().fill(testEmail)
    await page.locator('input[type="password"]').first().fill('AuthTest1234!')
    await page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")').first().click()

    // Should redirect away from /login
    await page.waitForURL(url => !url.pathname.includes('/login'), { timeout: 10000 })
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('authenticated user can access protected pages', async ({ page }) => {
    // Inject token directly (faster than UI login)
    await page.goto('/login')
    await page.evaluate((token) => {
      localStorage.setItem('airex-token', token)
      localStorage.setItem('airex-token-expiry', String(Date.now() + 86400000))
    }, testToken)

    await page.goto('/incidents')
    // Should not redirect to login
    await page.waitForTimeout(2000)
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('unauthenticated user is redirected to login', async ({ page }) => {
    // No token set
    await page.goto('/incidents')
    await page.waitForURL(/\/login/, { timeout: 8000 })
    await expect(page).toHaveURL(/\/login/)
  })

  test('token refresh keeps session alive', async ({ request }) => {
    // Get a fresh login to get refresh token
    const res = await request.post(`${API}/api/v1/auth/login`, {
      data: { email: testEmail, password: 'AuthTest1234!' },
    })
    const body = await res.json()
    expect(body.refresh_token).toBeTruthy()

    // Use refresh token to get new access token
    const refreshRes = await request.post(`${API}/api/v1/auth/refresh`, {
      data: { refresh_token: body.refresh_token },
    })
    expect(refreshRes.status()).toBe(200)
    const refreshBody = await refreshRes.json()
    expect(refreshBody.access_token).toBeTruthy()
    expect(refreshBody.access_token).not.toBe(body.access_token)
  })

  test('rate limiting blocks excessive login attempts', async ({ request }) => {
    // auth_rate_limit is 5 req/60s — send 7 rapid requests
    const attempts = Array.from({ length: 7 }, () =>
      request.post(`${API}/api/v1/auth/login`, {
        data: { email: 'flood@example.com', password: 'wrong' },
      })
    )
    const responses = await Promise.all(attempts)
    const statuses = responses.map(r => r.status())
    const blocked = statuses.filter(s => s === 429)
    expect(blocked.length).toBeGreaterThan(0)
  })
})
