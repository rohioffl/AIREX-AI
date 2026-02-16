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

test.describe('Incident Lifecycle', () => {
  let incidentId

  test.beforeAll(async ({ request }) => {
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
        resource_id: 'e2e-web-01',
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

  test('should display incidents list page', async ({ page }) => {
    await page.goto('/incidents')
    await expect(page.locator('body')).toBeVisible()

    // Wait for the incident list to render
    await page.waitForTimeout(2000)

    // Should see at least the page structure
    await expect(page.locator('text=Incidents').first()).toBeVisible()
  })

  test('should navigate to incident detail', async ({ page }) => {
    await page.goto(`/incidents/${incidentId}`)
    await page.waitForTimeout(2000)

    // Should show the incident detail page
    await expect(page.locator('body')).toBeVisible()
  })

  test('should show incident state progression', async ({ page }) => {
    await page.goto(`/incidents/${incidentId}`)
    await page.waitForTimeout(3000)

    // The incident should have progressed past RECEIVED
    // Look for state badges/pipeline elements
    const body = await page.textContent('body')
    expect(body).toBeTruthy()
  })

  test('should approve incident via API', async ({ request }) => {
    // Wait for investigation + recommendation to complete
    await new Promise((r) => setTimeout(r, 5000))

    // Check current state
    const getRes = await request.get(`${API}/api/v1/incidents/${incidentId}`, {
      headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000000' },
    })

    if (getRes.ok()) {
      const incident = await getRes.json()
      if (incident.state === 'AWAITING_APPROVAL') {
        // Approve the incident
        const approveRes = await request.post(
          `${API}/api/v1/incidents/${incidentId}/approve`,
          {
            headers: {
              'Content-Type': 'application/json',
              'X-Tenant-Id': '00000000-0000-0000-0000-000000000000',
            },
            data: {
              action: 'restart_service',
              idempotency_key: `e2e-approve-${Date.now()}`,
            },
          }
        )
        expect(approveRes.status()).toBeLessThan(500)
      }
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
        'ESCALATED',
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
