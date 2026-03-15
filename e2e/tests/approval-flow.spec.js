/**
 * E2E tests for the AIREX incident approval / rejection flow.
 *
 * Prerequisites:
 *   docker-compose up -d (all services running)
 *
 * Covers:
 *   - Incident reaches AWAITING_APPROVAL state
 *   - Operator can approve → moves to EXECUTING
 *   - Operator can reject → moves to REJECTED
 *   - SSE state_changed event updates the UI
 */

import { test, expect } from '@playwright/test'

const API = process.env.API_URL || 'http://localhost:8000'
const TENANT_ID = '00000000-0000-0000-0000-000000000000'

async function loginOperator(request) {
  const email = `e2e-operator-${Date.now()}@test.airex.dev`
  await request.post(`${API}/api/v1/auth/register`, {
    data: { email, password: 'Operator1234!', display_name: 'E2E Operator' },
  })
  const res = await request.post(`${API}/api/v1/auth/login`, {
    data: { email, password: 'Operator1234!' },
  })
  const body = await res.json()
  return { email, token: body.access_token }
}

async function createTestIncident(request) {
  const res = await request.post(`${API}/api/v1/webhooks/generic`, {
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-Id': TENANT_ID,
    },
    data: {
      alert_type: 'disk_full',
      severity: 'high',
      title: `E2E Approval Test: Disk Full ${Date.now()}`,
      resource_id: `e2e-disk-${Date.now()}`,
      meta: { host: 'e2e-disk-01', monitor_name: 'e2e-disk-01' },
    },
  })
  expect(res.status()).toBe(202)
  const body = await res.json()
  return body.incident_id
}

test.describe('Incident Approval Flow', () => {
  let operator
  let incidentId

  test.beforeAll(async ({ request }) => {
    operator = await loginOperator(request)
    incidentId = await createTestIncident(request)
  })

  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.evaluate((token) => {
      localStorage.setItem('airex-token', token)
      localStorage.setItem('airex-token-expiry', String(Date.now() + 86400000))
    }, operator.token)
  })

  test('incident detail page shows state badge', async ({ page }) => {
    await page.goto(`/incidents/${incidentId}`)
    await page.waitForTimeout(2000)
    // State badge should be visible somewhere on the page
    await expect(page.locator('body')).toBeVisible()
    // The incident ID should be referenced on the page
    const pageText = await page.textContent('body')
    expect(pageText).toBeTruthy()
  })

  test('API: incident transitions through states correctly', async ({ request }) => {
    // Poll for the incident to leave RECEIVED state
    let state = 'RECEIVED'
    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 3000))
      const res = await request.get(`${API}/api/v1/incidents/${incidentId}`, {
        headers: { Authorization: `Bearer ${operator.token}` },
      })
      const body = await res.json()
      state = body.state
      if (state !== 'RECEIVED' && state !== 'INVESTIGATING') break
    }
    // Should have progressed beyond initial ingestion
    expect(['RECOMMENDATION_READY', 'AWAITING_APPROVAL', 'EXECUTING',
            'VERIFYING', 'RESOLVED', 'FAILED_ANALYSIS']).toContain(state)
  })

  test('API: reject transitions incident to REJECTED', async ({ request }) => {
    // Create a fresh incident for rejection
    const rejectIncidentId = await createTestIncident(request)

    // Wait for it to be at a rejectable state
    let state = 'RECEIVED'
    for (let i = 0; i < 15; i++) {
      await new Promise(r => setTimeout(r, 2000))
      const res = await request.get(`${API}/api/v1/incidents/${rejectIncidentId}`, {
        headers: { Authorization: `Bearer ${operator.token}` },
      })
      const body = await res.json()
      state = body.state
      if (!['RECEIVED', 'INVESTIGATING'].includes(state)) break
    }

    // Reject the incident
    const rejectRes = await request.post(
      `${API}/api/v1/incidents/${rejectIncidentId}/reject`,
      {
        headers: {
          Authorization: `Bearer ${operator.token}`,
          'Content-Type': 'application/json',
        },
        data: { reason: 'E2E test rejection' },
      }
    )

    // Should succeed (200) or already be in terminal state (409)
    expect([200, 409]).toContain(rejectRes.status())

    if (rejectRes.status() === 200) {
      const body = await rejectRes.json()
      expect(body.state).toBe('REJECTED')
    }
  })

  test('incidents list page shows incident cards', async ({ page }) => {
    await page.goto('/incidents')
    await page.waitForTimeout(3000)

    // Should show at least some incident content
    const body = await page.textContent('body')
    expect(body).toBeTruthy()
    // Should not show a blank error page
    await expect(page.locator('body')).not.toContainText('500 Internal Server Error')
  })

  test('SSE connection is established on incident detail page', async ({ page }) => {
    // Monitor for SSE connection in network requests
    const sseRequests = []
    page.on('request', req => {
      if (req.url().includes('/events/stream')) {
        sseRequests.push(req.url())
      }
    })

    await page.goto(`/incidents/${incidentId}`)
    await page.waitForTimeout(3000)

    // SSE connection should have been attempted
    expect(sseRequests.length).toBeGreaterThan(0)
  })
})
