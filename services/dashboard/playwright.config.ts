import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end tests of the dashboard against the running stack (test plan 3.5: ST-02 to ST-05, SEC-08).
 * Start the stack first (`docker compose up -d` in the repository root), then `npx playwright test` here.
 * e2e/global-setup.ts prepares a test account and an imported port scan before the tests run.
 */
export default defineConfig({
  testDir: './e2e',
  testMatch: '*.e2e.ts', // not *.test.ts, so vitest doesn't pick them up
  globalSetup: './e2e/global-setup.ts',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1, // one stack, one database: the tests run one after another
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
