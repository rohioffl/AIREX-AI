import { expect, test } from '@playwright/test'

function createMockJwt(payload) {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString('base64url')
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(payload)}.signature`
}

async function bootstrapAdminSession(page) {
  const accessToken = createMockJwt({
    sub: 'admin@example.com',
    role: 'org_admin',
    tenant_id: 'tenant-1',
    user_id: 'user-1',
  })

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        user: {
          id: 'user-1',
          email: 'admin@example.com',
          display_name: 'Admin User',
          role: 'org_admin',
          tenant_id: 'tenant-1',
        },
        organization_memberships: [{ organization_id: 'org-1', role: 'org_admin', organization_name: 'Ankercloud' }],
        tenant_memberships: [],
        active_organization: { id: 'org-1', name: 'Ankercloud', slug: 'ankercloud' },
        active_tenant: { id: 'tenant-1', name: 'uno-secur', display_name: 'UnoSecur', organization_id: 'org-1' },
        tenants: [{ id: 'tenant-1', name: 'uno-secur', display_name: 'UnoSecur', organization_id: 'org-1' }],
        projects: [{ id: 'project-1', name: 'Project-1', slug: 'project-1' }],
      }),
    })
  })

  await page.route('**/api/v1/incidents/**', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, has_more: false }),
      })
      return
    }
    await route.fallback()
  })

  await page.route('**/api/v1/organizations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ id: 'org-1', name: 'Ankercloud', slug: 'ankercloud', status: 'active', tenant_count: 1 }]),
    })
  })

  await page.route('**/api/v1/organizations/org-1/tenants', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'tenant-1',
          name: 'uno-secur',
          display_name: 'UnoSecur',
          cloud: 'aws',
          is_active: true,
          organization_id: 'org-1',
          organization_name: 'Ankercloud',
          credential_status: 'configured',
          server_count: 3,
        },
      ]),
    })
  })

  await page.route('**/api/v1/tenants/tenant-1/projects', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ id: 'project-1', tenant_id: 'tenant-1', name: 'Project-1', slug: 'project-1', description: 'Core API', is_active: true }]),
    })
  })

  await page.route('**/api/v1/tenants/tenant-1/integrations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{
        id: 'integration-1',
        tenant_id: 'tenant-1',
        integration_type_id: 'type-1',
        integration_type_key: 'site24x7',
        name: 'Primary Site24x7',
        slug: 'primary-site24x7',
        enabled: true,
        config_json: {},
        status: 'configured',
        webhook_path: '/api/v1/webhooks/site24x7/integration-1',
      }]),
    })
  })

  await page.route('**/api/v1/integrations/integration-1/test', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'verified', integration_id: 'integration-1', tenant_id: 'tenant-1' }),
    })
  })

  await page.route('**/api/v1/integrations/integration-1/sync-monitors', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'synced', integration_id: 'integration-1', monitor_count: 0 }),
    })
  })

  await page.goto('/login')
  await page.evaluate(({ token }) => {
    localStorage.setItem('airex-token', token)
    localStorage.setItem('airex-token-expiry', String(Date.now() + 60 * 60 * 1000))
    localStorage.setItem('airex-active-tenant-id', 'tenant-1')
  }, { token: accessToken })
}

test.describe('Admin workspace routes', () => {
  test.beforeEach(async ({ page }) => {
    await bootstrapAdminSession(page)
  })

  test('organizations route renders the dedicated organization workspace', async ({ page }) => {
    await page.goto('/admin/organizations')
    await expect(page.getByRole('heading', { name: 'Organization Admin' })).toBeVisible()
    await expect(page.locator('option[value="org-1"]')).toHaveText('Ankercloud')
    await expect(page.getByText('UnoSecur').first()).toBeVisible()
  })

  test('workspace route shows tenant projects', async ({ page }) => {
    await page.goto('/admin/workspaces')
    await expect(page.getByRole('heading', { name: 'Tenant Workspaces' })).toBeVisible()
    await expect(page.getByText('Projects · UnoSecur')).toBeVisible()
  })

  test('integrations route shows webhook path and supports verify/sync', async ({ page }) => {
    await page.goto('/admin/integrations')
    await expect(page.getByRole('heading', { name: 'Monitoring Integrations' })).toBeVisible()
    await expect(page.getByText('Integrations · UnoSecur')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Add Integration' })).toBeVisible()
  })
})
