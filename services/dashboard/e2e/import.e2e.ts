import { expect, test } from '@playwright/test'
import { attacker, signIn } from './helpers'

// Checks the whole chain the other scenarios build on: stack, import, detection, login and the alert list.
test('an imported port scan shows up as an alert and opens with its explanation', async ({ page }) => {
  await signIn(page)
  await page.goto(`/alerts?src=${attacker()}`)

  const row = page.getByRole('row').filter({ hasText: attacker() }).first()
  await expect(row).toBeVisible()
  await expect(row).toContainText(/port scan/i)

  await row.getByRole('link').first().click()
  await expect(page.getByRole('heading', { name: 'Explanation' })).toBeVisible()
  await expect(page.getByText(/distinct destination ports/)).toBeVisible()
})
