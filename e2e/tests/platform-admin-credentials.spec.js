/**
 * Real browser login using `../../.local/testing-credentials.txt` (gitignored)
 * or E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD. Skips when neither is available.
 *
 * Requires: Vite + API reachable from BASE_URL (default http://localhost:5173).
 *
 * If the API returns "Rate limit exceeded" for `/auth/admin/login`, the test skips
 * (common when re-running quickly). Wait ~60s or relax rate limits for local E2E.
 */
import { expect, test } from '@playwright/test'
import fs from 'fs'
import path from 'path'

/** Repo root when Playwright cwd is `e2e/` (default `npm run test` from e2e). */
function repoRootFromCwd() {
  return path.resolve(process.cwd(), '..')
}

function readLocalCredentials() {
  const fromEnvEmail = process.env.E2E_ADMIN_EMAIL?.trim()
  const fromEnvPassword = process.env.E2E_ADMIN_PASSWORD?.trim()
  if (fromEnvEmail && fromEnvPassword) {
    return { email: fromEnvEmail, password: fromEnvPassword, source: 'env' }
  }

  const repoRoot = repoRootFromCwd()
  const filePath = path.join(repoRoot, '.local', 'testing-credentials.txt')
  if (!fs.existsSync(filePath)) {
    return null
  }
  const raw = fs.readFileSync(filePath, 'utf8')
  const emailMatch = raw.match(/^\s*Email:\s*(.+)$/im)
  const passwordMatch = raw.match(/^\s*Password:\s*(.+)$/im)
  const email = emailMatch?.[1]?.trim()
  const password = passwordMatch?.[1]?.trim()
  if (!email || !password) {
    return null
  }
  return { email, password, source: 'file' }
}

const creds = readLocalCredentials()

test.describe('Platform admin (local credentials file)', () => {
  test.skip(
    !creds,
    'Skipped: add .local/testing-credentials.txt with Email: and Password: lines (gitignored), or set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD',
  )

  test('signs in at /admin/login and reaches platform shell', async ({ page }) => {
    await page.goto('/admin/login')

    await page.locator('input[type="email"]').fill(creds.email)
    await page.locator('input[type="password"]').fill(creds.password)
    await page.getByRole('button', { name: /authorize admin session/i }).click()

    const onAdminLogin = () => /\/admin\/login\/?$/.test(new URL(page.url()).pathname)
    const deadline = Date.now() + 35_000
    while (Date.now() < deadline && onAdminLogin()) {
      if (await page.getByText(/rate limit exceeded/i).isVisible().catch(() => false)) {
        test.skip(
          true,
          'Admin login hit API rate limit (e.g. 5/min). Wait ~60s or relax limits for E2E.',
        )
      }
      await new Promise((r) => setTimeout(r, 250))
    }

    if (onAdminLogin()) {
      const errText =
        (await page.locator('div.text-red-400').first().textContent().catch(() => null))?.trim() ||
        null
      throw new Error(
        errText
          ? `Still on /admin/login after submit: ${errText}`
          : 'Still on /admin/login after submit (no error banner — check network/API).',
      )
    }

    await expect(page).toHaveURL(/\/admin/)

    await expect(page.getByText('Platform Admin', { exact: false }).first()).toBeVisible({
      timeout: 15_000,
    })
  })
})
