// Isolated first-visit dialog acceptance. The planner's seeded background is
// present, while fonts and geographic basemaps use local deterministic fixtures.
const fs = require('node:fs'), path = require('node:path'), net = require('node:net')
const assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const playwrightPath = process.env.M2_PLAYWRIGHT || 'playwright'
const { chromium } = require(playwrightPath)
const root = path.resolve(__dirname, '../..'), out = path.join(root, '.cache/preferences-browser')
const keys = { state: 'rr.preferences.v2', profile: 'rr.weight-profile.v2', events: 'rr.preference-events.v2' }
const dimensions = ['time', 'transfers', 'walking', 'fare', 'comfort', 'reliability', 'carbon', 'freshness', 'accessibility']
const checks = [], errors = [], evidence = { passed: false, checks, audits: [], layouts: [], errors }
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
let server, browser, currentPage, logs = '', web
let axeSource
try { axeSource = fs.readFileSync(require.resolve('axe-core', { paths: [path.dirname(require.resolve(playwrightPath))] }), 'utf8') }
catch (error) { if (process.env.PREFERENCE_REQUIRE_AXE === 'true') throw error }
fs.mkdirSync(out, { recursive: true })
function pass(name) { checks.push(name); console.log('PASS ' + name) }
async function freePort() {
  const socket = net.createServer(); await new Promise(resolve => socket.listen(0, '127.0.0.1', resolve))
  const port = socket.address().port; await new Promise(resolve => socket.close(resolve)); return port
}
function url(view) {
  const result = new URL(web); result.searchParams.set('data', 'seed')
  if (view) result.searchParams.set('view', view); else result.searchParams.delete('view')
  return result.href
}
async function ready() {
  for (let attempt = 0; attempt < 150; attempt++) {
    if (server?.exitCode != null) throw new Error('Vite stopped: ' + logs)
    try { if ((await fetch(web)).ok) return } catch {}
    await pause(100)
  }
  throw new Error('Frontend unavailable: ' + logs)
}
const read = (page, key) => page.evaluate(key => JSON.parse(localStorage.getItem(key) || 'null'), key)
async function stateAt(page, phase, dimension) {
  await page.waitForFunction(({ key, phase, dimension }) => {
    const value = JSON.parse(localStorage.getItem(key) || 'null')
    return value?.phase === phase && !value.pending && (!dimension || value.queue[value.cursor] === dimension)
  }, { key: keys.state, phase, dimension })
  if (phase === 'question') await page.getByRole('radiogroup').waitFor({ state: 'visible' })
}
async function choose(page, index = 0) {
  const before = await read(page, keys.state)
  await page.getByRole('radio').nth(index).click()
  await page.waitForFunction(({ key, cursor, phase }) => {
    const value = JSON.parse(localStorage.getItem(key) || 'null')
    return value && !value.pending && (value.cursor !== cursor || value.phase !== phase)
  }, { key: keys.state, cursor: before.cursor, phase: before.phase })
}
async function audit(page, name) {
  if (!axeSource) return
  await pause(350)
  await page.addScriptTag({ content: axeSource })
  const violations = await page.evaluate(async () => (await axe.run(document, {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] },
  })).violations.map(item => ({ id: item.id, impact: item.impact, nodes: item.nodes.map(node => ({ target: node.target, reason: node.failureSummary })) })))
  evidence.audits.push({ name, violations })
  assert.deepEqual(violations, [], `${name}: automated WCAG AA audit`)
}
async function setup(options = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, ...options })
  // These resources are unrelated to the questionnaire. Avoid external requests
  // without hiding application failures or replacing its scripts/data.
  await context.route('https://fonts.googleapis.com/**', route => route.fulfill({ status: 200, contentType: 'text/css', body: '' }))
  await context.route('https://tiles.openfreemap.org/styles/positron', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ version: 8, sources: {}, layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#e8ede5' } }] }) }))
  await context.route('https://tile.openstreetmap.org/**', route => route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64') }))
  const page = await context.newPage(); currentPage = page; page.setDefaultTimeout(15000)
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
  return { context, page }
}
async function geometry(page, name) {
  const value = await page.locator('dialog[open]').evaluate(dialog => {
    const r = dialog.getBoundingClientRect(), backdrop = getComputedStyle(dialog, '::backdrop')
    return { name: '', x: r.x, y: r.y, width: r.width, height: r.height, viewportWidth: innerWidth, viewportHeight: innerHeight,
      documentWidth: document.documentElement.scrollWidth, nativeModal: dialog.matches(':modal'),
      inertBackground: Array.from(document.querySelectorAll('[inert]')).some(element => !dialog.contains(element) && !element.contains(dialog)),
      backdropFilter: backdrop.backdropFilter, backdropColor: backdrop.backgroundColor }
  })
  value.name = name; evidence.layouts.push(value)
  assert.ok(value.nativeModal, 'Questionnaire must use the native modal top layer')
  assert.ok(value.inertBackground, 'The visible background must be inert')
  assert.ok(value.x >= -1 && value.y >= -1 && value.x + value.width <= value.viewportWidth + 1 && value.y + value.height <= value.viewportHeight + 1, `${name}: dialog fits viewport`)
  assert.ok(value.documentWidth <= value.viewportWidth + 1, `${name}: no horizontal overflow`)
  if (value.viewportWidth >= 1000) {
    assert.ok(value.width < value.viewportWidth - 48 && value.height < value.viewportHeight - 48, 'Desktop dialog must leave surrounding space')
    assert.ok(Math.abs(value.x + value.width / 2 - value.viewportWidth / 2) < 3 && Math.abs(value.y + value.height / 2 - value.viewportHeight / 2) < 3, 'Desktop dialog is centered')
    assert.match(value.backdropFilter, /blur\(/, 'Background must be blurred')
  }
}
async function percentages(page) {
  const values = await page.locator('[data-weight-percent]').evaluateAll(elements => elements.map(element => Number(element.getAttribute('data-weight-percent'))))
  assert.equal(values.length, 9, 'All nine dimensions must be visible in the profile')
  assert.equal(values.reduce((sum, value) => sum + value, 0), 100, 'Displayed shares must total 100%')
}
async function focusInside(page) {
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press(i < 6 ? 'Tab' : 'Shift+Tab')
    assert.ok(await page.locator('dialog[open]').evaluate(dialog => dialog.contains(document.activeElement)), 'Keyboard focus must remain in the dialog')
  }
}
;(async () => {
  web = process.env.PREFERENCE_BASE_URL || `http://127.0.0.1:${await freePort()}`
  if (!process.env.PREFERENCE_BASE_URL) {
    const production = process.env.PREFERENCE_PRODUCTION === 'true'
    const args = ['node_modules/vite/bin/vite.js', ...(production ? ['preview'] : []), '--host', '127.0.0.1', '--port', new URL(web).port, '--strictPort']
    server = spawn(process.execPath, args, { cwd: path.join(root, 'frontend'), windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
    server.stdout.on('data', chunk => logs += chunk); server.stderr.on('data', chunk => logs += chunk); server.on('error', error => logs += error.message)
  }
  await ready()
  browser = await chromium.launch({ headless: true, ...(process.env.M2_BROWSER_CHANNEL ? { channel: process.env.M2_BROWSER_CHANNEL } : {}) })
  const { context, page } = await setup()
  await page.goto(url()); await page.getByRole('button', { name: '开始探索', exact: true }).waitFor(); await pause(550)
  await geometry(page, 'desktop-welcome'); await focusInside(page); await audit(page, 'welcome')
  await page.screenshot({ path: path.join(out, '01-welcome-desktop.png') })
  pass('first visit opens a centered native dialog over a blurred inert background and traps focus')
  await page.getByRole('button', { name: '开始探索', exact: true }).focus(); await page.keyboard.press('Enter'); await stateAt(page, 'question', 'time')
  assert.equal(await page.getByRole('radio').count(), 3)
  const started = Date.now(); await choose(page, 0); await stateAt(page, 'question', 'transfers')
  assert.ok(Date.now() - started >= 450, 'Selection leaves time for map feedback before advancing')
  await choose(page, 2); await stateAt(page, 'question', 'walking')
  await page.getByRole('button', { name: '上一题', exact: true }).click(); await stateAt(page, 'question', 'transfers')
  assert.equal(await page.getByRole('radio').nth(2).getAttribute('aria-checked'), 'true', 'Back preserves the earlier answer')
  await page.getByRole('radio').nth(2).focus(); await page.keyboard.press('ArrowUp'); await page.keyboard.press('Enter'); await stateAt(page, 'question', 'walking')
  assert.equal((await read(page, keys.state)).answers.transfers, 'transfers-1')
  await audit(page, 'question'); await page.screenshot({ path: path.join(out, '02-question-desktop.png') })
  await page.getByRole('button', { name: '跳过', exact: true }).click(); await stateAt(page, 'summary')
  await page.getByRole('heading', { name: '你的出行偏好', exact: true }).waitFor()
  assert.equal((await read(page, keys.state)).answers.walking, null)
  await percentages(page); await audit(page, 'core-summary'); await page.screenshot({ path: path.join(out, '03-core-summary.png') })
  pass('three distinct core questions support automatic advance, keyboard choices, back and skipped evidence')
  await page.getByRole('button', { name: '继续完善', exact: true }).click(); await stateAt(page, 'question', 'fare')
  await page.getByRole('radio').nth(0).click(); await page.getByRole('button', { name: '上一题', exact: true }).click(); await stateAt(page, 'question', 'walking')
  await pause(850); assert.equal((await read(page, keys.state)).queue[(await read(page, keys.state)).cursor], 'walking', 'Back cancels pending automatic advance')
  assert.equal((await read(page, keys.state)).answers.fare, 'fare-0', 'Later answers are retained for revisiting')
  await page.getByRole('button', { name: '跳过', exact: true }).click(); await stateAt(page, 'question', 'fare')
  assert.equal(await page.getByRole('radio').nth(0).getAttribute('aria-checked'), 'true')
  await choose(page, 1); await stateAt(page, 'question', 'comfort')
  await page.reload(); await stateAt(page, 'question', 'comfort')
  assert.equal((await read(page, keys.state)).answers.fare, 'fare-1', 'Reload preserves progress')
  for (const [index, dimension] of ['comfort', 'reliability', 'carbon', 'freshness', 'accessibility'].entries()) {
    await stateAt(page, 'question', dimension); await choose(page, index % 3)
  }
  await stateAt(page, 'summary'); await percentages(page); await audit(page, 'complete-summary')
  await page.getByRole('button', { name: '完成', exact: true }).click(); await stateAt(page, 'complete')
  await page.getByRole('heading', { name: /^你的偏好，已就绪。?$/ }).waitFor()
  const profile = await read(page, keys.profile), events = await read(page, keys.events)
  assert.deepEqual(Object.keys(profile.weights).sort(), [...dimensions].sort())
  assert.ok(Math.abs(Object.values(profile.weights).reduce((sum, value) => sum + value, 0) - 1) < 1e-12)
  assert.equal(profile.evidence.walking.status, 'skipped'); assert.equal(profile.evidence.walking.raw, .5)
  for (const dimension of dimensions.filter(id => id !== 'walking')) assert.equal(profile.evidence[dimension].status, 'collected')
  for (const event of ['start', 'answer', 'skip', 'back', 'continue', 'complete']) assert.ok(events.some(item => item.event === event), `Records ${event}`)
  assert.ok(await page.locator('[aria-live]').count(), 'Switches and weights have a live announcement region')
  const downloadPromise = page.waitForEvent('download'); await page.getByRole('button', { name: /导出画像/ }).click()
  const download = await downloadPromise, downloaded = path.join(out, 'exported-profile.json'); await download.saveAs(downloaded)
  const exported = JSON.parse(fs.readFileSync(downloaded, 'utf8')); assert.deepEqual(exported.weights, profile.weights)
  await audit(page, 'complete'); await page.screenshot({ path: path.join(out, '04-complete.png') })
  pass('all six additional dimensions, reload, cancellation, normalized explainable profile, event history and JSON export')
  await page.getByRole('button', { name: '开始规划', exact: true }).click(); await page.locator('dialog[open]').waitFor({ state: 'hidden' })
  await page.reload(); assert.equal(await page.locator('dialog[open]').count(), 0, 'Completed visitors return to the planner')
  await page.goto(url('preferences')); await page.locator('dialog[open]').waitFor()
  await page.getByRole('button', { name: '暂时关闭引导', exact: true }).click(); await page.locator('dialog[open]').waitFor({ state: 'hidden' })
  await context.close()
  const bypass = await setup({ reducedMotion: 'reduce' }); await bypass.page.goto(url('planner'))
  await bypass.page.getByRole('button', { name: /^Find resilient routes/ }).waitFor()
  assert.equal(await bypass.page.locator('dialog[open]').count(), 0)
  assert.equal(await bypass.page.evaluate(() => Object.keys(localStorage).length + Object.keys(sessionStorage).length), 0, 'Explicit planner entry does not write onboarding storage')
  await bypass.context.close(); pass('completion, explicit reopen/close and clean planner bypass')
  for (const width of [320, 390, 768]) {
    const mobile = await setup({ viewport: { width, height: 844 }, reducedMotion: 'reduce' })
    await mobile.page.goto(url()); await mobile.page.getByRole('button', { name: '开始探索', exact: true }).waitFor(); await pause(120)
    await geometry(mobile.page, `${width}-welcome`); await focusInside(mobile.page)
    await mobile.page.getByRole('button', { name: '开始探索', exact: true }).click(); await stateAt(mobile.page, 'question', 'time')
    await geometry(mobile.page, `${width}-question`); await choose(mobile.page, 1); await stateAt(mobile.page, 'question', 'transfers')
    await audit(mobile.page, `${width}-reduced-motion-question`)
    assert.equal(await mobile.page.evaluate(() => document.getAnimations().filter(animation => animation.playState === 'running' && Number(animation.effect?.getTiming().duration) > 100).length), 0, 'Reduced motion has no long running CSS animations')
    await mobile.page.screenshot({ path: path.join(out, `05-mobile-${width}.png`) })
    await mobile.page.getByRole('button', { name: '跳过', exact: true }).click(); await stateAt(mobile.page, 'question', 'walking')
    await mobile.page.getByRole('button', { name: '跳过', exact: true }).click(); await stateAt(mobile.page, 'summary')
    await percentages(mobile.page); await geometry(mobile.page, `${width}-summary`); await audit(mobile.page, `${width}-summary`)
    await mobile.page.getByRole('button', { name: '完成', exact: true }).click(); await stateAt(mobile.page, 'complete')
    await mobile.page.getByRole('button', { name: '开始规划', exact: true }).scrollIntoViewIfNeeded()
    assert.equal((await read(mobile.page, keys.profile)).collected, 1, 'A three-question profile can finish with skipped neutral dimensions')
    await mobile.page.screenshot({ path: path.join(out, `06-mobile-complete-${width}.png`) })
    await mobile.context.close()
  }
  pass('320, 390 and 768 px layouts, keyboard focus and reduced-motion accessibility')
  assert.deepEqual(errors, [], 'No console errors or uncaught application exceptions')
  evidence.passed = true; evidence.axeAvailable = Boolean(axeSource); console.log(JSON.stringify({ passed: true, checks: checks.length, audits: evidence.audits.length }))
})().catch(async error => {
  console.error(error.stack)
  if (currentPage && !currentPage.isClosed()) {
    console.error('Visible DOM: ' + (await currentPage.locator('body').innerText().catch(() => '')).slice(-10000))
    await currentPage.screenshot({ path: path.join(out, 'failure.png'), fullPage: true }).catch(() => {})
  }
  process.exitCode = 1
}).finally(async () => {
  fs.writeFileSync(path.join(out, 'evidence.json'), JSON.stringify(evidence, null, 2) + '\n')
  await browser?.close()
  if (server && server.exitCode === null) {
    if (process.platform === 'win32') await new Promise(resolve => spawn('taskkill', ['/PID', String(server.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }).on('exit', resolve))
    else server.kill('SIGTERM')
  }
})
