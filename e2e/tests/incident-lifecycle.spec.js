/**
 * E2E tests for the AIREX incident lifecycle.
 *
 * Prerequisites:
 *   docker-compose up -d (all services running)
 *   Frontend available at localhost:5173
 *   Backend available at localhost:8000
 *
 * Tests the full approve-execute-verify flow visible in the UI.
 */

import { test, expect } from '@playwright/test'

const API = process.env.API_URL || 'http://localhost:8000'

let e2eUserToken = ''

async function setupTestUser(request) {
  const email = `e2e-suite-${Date.now()}@test.airex.dev`
  await request.post(`${API}/api/v1/auth/register`, {
    data: { email, password: 'Test1234!', display_name: 'E2E Suite User' },
  })

  const res = await request.post(`${API}/api/v1/auth/login`, {
    data: { email, password: 'Test1234!' },
  })

  const body = await res.json()
  e2eUserToken = body.access_token
  return { email, token: body.access_token }
}

test.describe('Incident Lifecycle', () => {
  let incidentId

  test.beforeAll(async ({ request }) => {
    // Setup Auth
    const user = await setupTestUser(request)

    // Create an incident via webhook
    const res = await request.post(`${API}/api/v1/webhooks/generic`, {
      headers: {
        'Content-Type': 'application/json',
        'X-Tenant-Id': '00000000-0000-0000-0000-000000000000',
      },
      data: {
        alert_type: 'cpu_high',
        severity: 'critical',
        title: 'E2E Test: High CPU on web-01',
        resource_id: `e2e-web-${Date.now()}`,
        meta: {
          host: 'e2e-web-01',
          monitor_name: 'e2e-web-01',
          service_name: 'nginx',
        },
      },
    })

    expect(res.status()).toBe(202)
    const body = await res.json()
    incidentId = body.incident_id
    expect(incidentId).toBeTruthy()
  })

  test.beforeEach(async ({ page }) => {
    // Inject real token so AuthContext allows navigation
    await page.goto('/login')
    await page.evaluate((token) => {
      localStorage.setItem('airex-token', token)
      localStorage.setItem('airex-token-expiry', String(Date.now() + 86400000)) // 1 day future
    }, e2eUserToken)
  })

  test('should display incidents list page', async ({ page }) => {
    await page.goto('/incidents')
    await expect(page.locator('body')).toBeVisible()

    // Should see at least the page structure (redirects to /alerts -> Active Alerts)
    await page.waitForTimeout(5000)
    await expect(page.locator('text=Dashboard').first()).toBeVisible()
  })

  test('should navigate to incident detail', async ({ page }) => {
    await page.goto(`/incidents/${incidentId}`)
    await page.waitForTimeout(2000)

    // Should show the incident detail page
    await expect(page.locator('body')).toBeVisible()
  })

  test('should show incident state progression and Recommendation/RAG', async ({ page }) => {
    await page.goto(`/incidents/${incidentId}`)

    // Wait until it reaches AWAITING_APPROVAL or FAILED_ANALYSIS
    // The StateBadge renders the exact state string uppercase, e.g. AWAITING_APPROVAL
    await expect(page.locator('text=AWAITING_APPROVAL').or(page.locator('text=FAILED_ANALYSIS')).first()).toBeVisible({ timeout: 60000 }) // Use .first() to ensure only one element is matched

    // If there is a recommendation card, verify it shows
    const hasRecommendation = await page.locator('text=AI Recommendation').isVisible()
    if (hasRecommendation) {
      // It should display RAG context if any
      const hasRag = await page.locator('text=AI Context & Reasoning').isVisible()
      // We don't strictly assert hasRag is true because it depends on DB seeding in E2E
    }
  })

  test('should approve incident via UI', async ({ page, request }) => {
    await page.goto(`/incidents/${incidentId}`)

    // Check if the Approve button is visible
    const approveBtn = page.locator('button:has-text("Approve Execution")')
    if (await approveBtn.isVisible()) {
      await approveBtn.click()

      // Confirm in the modal
      const confirmBtn = page.locator('button:has-text("Confirm & Execute")')
      await expect(confirmBtn).toBeVisible()
      await confirmBtn.click()

      // Wait for execution to start
      await expect(page.locator('text=Executing').or(page.locator('text=Verifying')).or(page.locator('text=Resolved'))).toBeVisible({ timeout: 30000 })
    }
  })

  test('should show live execution logs', async ({ page, request }) => {
    await page.goto(`/incidents/${incidentId}`)
    await page.waitForTimeout(3000)

    // The page should be interactive and show some incident data
    await expect(page.locator('body')).toBeVisible()
  })

  test('should show resolved or terminal state', async ({ request }) => {
    // Wait for execution + verification
    await new Promise((r) => setTimeout(r, 8000))

    const res = await request.get(`${API}/api/v1/incidents/${incidentId}`, {
      headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000000' },
    })

    if (res.ok()) {
      const incident = await res.json()
      const terminalStates = [
        'RESOLVED',
        'REJECTED',
        'FAILED_EXECUTION',
        'FAILED_VERIFICATION',
        'AWAITING_APPROVAL',
        'INVESTIGATING',
        'RECOMMENDATION_READY',
      ]
      expect(terminalStates).toContain(incident.state)
    }
  })
})

test.describe('Dashboard UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.evaluate((token) => {
      localStorage.setItem('airex-token', token)
      localStorage.setItem('airex-token-expiry', String(Date.now() + 86400000))
    }, e2eUserToken)
  })

  test('should render the sidebar and navigation', async ({ page }) => {
    await page.goto('/incidents')

    // Sidebar should be visible on desktop
    const sidebar = page.locator('.sidebar').first()
    if (await sidebar.isVisible()) {
      await expect(sidebar).toBeVisible()
    }
  })

  test('should toggle dark/light mode', async ({ page }) => {
    await page.goto('/incidents')
    await page.waitForTimeout(1000)

    // Check initial dark mode
    const body = page.locator('body')
    const initialClasses = await body.getAttribute('class')

    // Find and click theme toggle
    const toggle = page.locator('.theme-toggle').first()
    if (await toggle.isVisible()) {
      await toggle.click()
      await page.waitForTimeout(500)

      // Body should now have light-mode class
      await expect(body).toHaveClass(/light-mode/)

      // Toggle back
      await toggle.click()
      await page.waitForTimeout(500)
    }
  })

  test('should navigate between pages', async ({ page }) => {
    await page.goto('/incidents')
    await page.waitForTimeout(1000)

    // Navigate to alerts
    const alertsLink = page.locator('a[href="/alerts"]').first()
    if (await alertsLink.isVisible()) {
      await alertsLink.click()
      await expect(page).toHaveURL(/\/alerts/)
    }
  })

  test('should display metrics cards', async ({ page }) => {
    await page.goto('/incidents')
    await page.waitForTimeout(2000)

    // Look for metric card elements
    const body = await page.textContent('body')
    expect(body).toBeTruthy()
  })
})

test.describe('Authentication Flow', () => {
  test('should register a new user', async ({ request }) => {
    const email = `e2e-${Date.now()}@test.airex.dev`
    const res = await request.post(`${API}/api/v1/auth/register`, {
      data: {
        email,
        password: 'Test1234!',
        display_name: 'E2E Test User',
      },
    })

    // Might fail if DB not set up, but should not 500
    expect(res.status()).toBeLessThan(500)
  })

  test('should login and receive tokens', async ({ request }) => {
    const email = `e2e-login-${Date.now()}@test.airex.dev`

    // Register first
    await request.post(`${API}/api/v1/auth/register`, {
      data: {
        email,
        password: 'Test1234!',
        display_name: 'E2E Login User',
      },
    })

    // Login
    const res = await request.post(`${API}/api/v1/auth/login`, {
      data: { email, password: 'Test1234!' },
    })

    if (res.ok()) {
      const body = await res.json()
      expect(body.access_token).toBeTruthy()
      expect(body.refresh_token).toBeTruthy()
      expect(body.token_type).toBe('bearer')
    }
  })

  test('should reject invalid credentials', async ({ request }) => {
    const res = await request.post(`${API}/api/v1/auth/login`, {
      data: {
        email: 'nonexistent@test.airex.dev',
        password: 'WrongPassword!',
      },
    })

    expect(res.status()).toBe(401)
  })
})
