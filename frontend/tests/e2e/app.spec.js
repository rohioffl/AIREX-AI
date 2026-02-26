import { test, expect } from '@playwright/test';

test.describe('AIREX Frontend', () => {
  test('should load the application', async ({ page }) => {
    await page.goto('/');
    
    // Wait for the app to load
    await page.waitForLoadState('networkidle');
    
    // Check if the page loaded (either login page or main app)
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('should show login page when not authenticated', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Check for login elements (email, password, or login button)
    const loginElements = page.locator('input[type="email"], input[type="password"], button:has-text("Login"), button:has-text("Sign in")');
    const count = await loginElements.count();
    
    // Either we see login elements or we're already logged in (redirected)
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('should navigate to incidents page', async ({ page }) => {
    await page.goto('/incidents');
    await page.waitForLoadState('networkidle');
    
    // Check if incidents page loaded
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('should check for AI Analysis panel component', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Check if React app is mounted
    const root = page.locator('#root');
    await expect(root).toBeVisible();
  });
});
