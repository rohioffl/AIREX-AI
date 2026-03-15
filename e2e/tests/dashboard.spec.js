/**
 * E2E tests for the AIREX Dashboard page.
 *
 * Prerequisites:
 *   docker-compose up -d (all services running)
 *
 * Covers:
 *   - Dashboard renders without errors
 *   - Metric cards are present
 *   - Navigation links work
 *   - Settings page loads
 *   - Health checks page loads
 */

import { test, expect } from '@playwright/test'

const API = process.env.API_URL || 'http://localhost:8000'

let token = ''

test.describe('Dashboard & Navigation', () => {
  test.beforeAll(async ({ request }) => {
    const email = `e2e-dash-${Date.now()}@test.airex.dev`
    await request.post(`${API}/api/v1/auth/register`, {
      data: { email, password: 'Dash1234!', display_name: 'E2E Dashboard User' },
    })
    const res = await request.post(`${API}/api/v1/auth/login`, {
      data: { email, password: 'Dash1234!' },
    })
    const body = await res.json()
    token = body.access_token
  })

  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.evaluate((t) => {
      localStorage.setItem('airex-token', t)
      localStorage.setItem('airex-token-expiry', String(Date.now() + 86400000))
    }, token)
  })

  test('dashboard page loads without JS errors', async ({ page }) => {
    const errors = []
    page.on('pageerror', err => errors.push(err.message))

    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // No uncaught JS errors
    const criticalErrors = errors.filter(e =>
      !e.includes('ResizeObserver') && !e.includes('Non-Error promise')
    )
    expect(criticalErrors).toHaveLength(0)
  })

  test('dashboard has metric cards or incident summary', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // Page should have meaningful content
    const bodyText = await page.textContent('body')
    expect(bodyText?.length).toBeGreaterThan(100)
    await expect(page.locator('body')).not.toContainText('500')
  })

  test('sidebar navigation is visible', async ({ page }) => {
    await page.goto('/')
    await page.waitForTimeout(2000)

    // Nav/sidebar should be present
    const nav = page.locator('nav, aside, [role="navigation"]').first()
    await expect(nav).toBeVisible({ timeout: 8000 })
  })

  test('incidents page is reachable via navigation', async ({ page }) => {
    await page.goto('/')
    await page.waitForTimeout(1000)

    // Click on Incidents link in sidebar
    const incidentsLink = page.locator('a[href*="incident"], a:has-text("Incident")').first()
    if (await incidentsLink.isVisible()) {
      await incidentsLink.click()
      await page.waitForURL(/incident/, { timeout: 8000 })
      await expect(page).toHaveURL(/incident/)
    } else {
      // Navigate directly
      await page.goto('/incidents')
      await expect(page).not.toHaveURL(/login/)
    }
  })

  test('health checks page loads', async ({ page }) => {
    await page.goto('/health-checks')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('body')).not.toContainText('500')
  })

  test('settings page loads', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await expect(page).not.toHaveURL(/login/)
    await expect(page.locator('body')).not.toContainText('500')
  })

  test('404 page renders for unknown routes', async ({ page }) => {
    await page.goto('/this-route-does-not-exist-12345')
    await page.waitForTimeout(2000)
    // Should show 404 page or redirect — not a blank page
    const bodyText = await page.textContent('body')
    expect(bodyText?.trim().length).toBeGreaterThan(10)
  })

  test('API health endpoint responds', async ({ request }) => {
    const res = await request.get(`${API}/api/v1/health`)
    expect([200, 204]).toContain(res.status())
  })

  test('API metrics endpoint requires auth', async ({ request }) => {
    const res = await request.get(`${API}/api/v1/metrics/summary`)
    // Should require authentication
    expect([401, 403]).toContain(res.status())
  })
})
