// Public navigation is folded below 1024 px; all helpers use actual controls.
const assert = require('node:assert/strict')

async function navigate(page, name) {
  // CSS responds to viewport changes before React commits its matchMedia state.
  // Wait for both to agree before opening a folded menu so the pending resize
  // handler cannot immediately close a menu we have just opened.
  await page.waitForFunction(() => {
    const menu = document.getElementById('navigation-toggle')
    const navigation = document.getElementById('main-navigation')
    if (!menu || !navigation) return false
    const compact = window.matchMedia('(max-width: 1023px)').matches
    const expanded = menu.getAttribute('aria-expanded') === 'true'
    const menuVisible = menu.getBoundingClientRect().width > 0
    return compact ? menuVisible && navigation.hidden === !expanded : !menuVisible && !navigation.hidden
  })
  const navigation = page.getByRole('navigation', { name: 'Main navigation', exact: true })
  const target = navigation.getByRole('button', { name, exact: true })
  if (!await target.isVisible()) {
    const toggle = page.locator('#navigation-toggle')
    await toggle.waitFor({ state: 'visible' })
    if (await toggle.getAttribute('aria-expanded') !== 'true') await toggle.click()
    await page.waitForFunction(() => document.getElementById('navigation-toggle')?.getAttribute('aria-expanded') === 'true' && !document.getElementById('main-navigation')?.hidden)
  }
  await target.waitFor({ state: 'visible' })
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
