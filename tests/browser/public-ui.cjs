// Public navigation is folded below 1024 px; all helpers use actual controls.
const assert = require('node:assert/strict')

async function navigate(page, name) {
  const navigation = page.getByRole('navigation', { name: 'Main navigation', exact: true })
  const target = navigation.getByRole('button', { name, exact: true })
  if (!await target.isVisible()) {
    const toggle = page.locator('#navigation-toggle')
    if (await toggle.isVisible()) await toggle.click()
  }
  await target.click()
}

async function signInAdministrator(page, api) {
  await page.goto(api + '/admin/')
  await page.getByLabel('Username', { exact: true }).fill('operator')
  await page.getByLabel('Password', { exact: true }).fill('local-test-password')
  await page.getByRole('button', { name: /^Sign in/ }).click()
  await page.getByRole('button', { name: /Reports & Review$/ }).click()
  await page.getByRole('button', { name: 'Refresh reports', exact: true }).waitFor()
}

async function assertRemovedPages(page) {
  const navigation = page.getByRole('navigation', { name: 'Main navigation', exact: true })
  for (const name of ['Compare', 'Simulation', 'Review']) {
    assert.equal(await navigation.getByRole('button', { name, exact: true, includeHidden: true }).count(), 0)
  }
  assert.equal(await page.getByRole('button', { name: 'Open the review desk →', includeHidden: true }).count(), 0)
  assert.equal(await page.getByText('Checking public updates every 3s', { exact: true }).count(), 0)
}

module.exports = { navigate, signInAdministrator, assertRemovedPages }
