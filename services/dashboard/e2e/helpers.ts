import { expect, type Page } from '@playwright/test'

/** Address of the port scan that global-setup.ts imported; it has a HIGH port scan alert. */
export function attacker(): string {
  const value = process.env.E2E_ATTACKER
  if (!value) throw new Error('E2E_ATTACKER is not set, run the tests with `npx playwright test`')
  return value
}

/** Signs in with the test account of global-setup.ts (an admin) and waits until the login page is gone. */
export async function signIn(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Username').fill(process.env.E2E_USER ?? '')
  await page.getByLabel('Password').fill(process.env.E2E_PASSWORD ?? '')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).not.toHaveURL(/\/login/)
}
