// Run with M2_PLAYWRIGHT pointing at an installed Playwright package when it
// is not available locally. All reports and credentials are isolated fixtures.
const fs = require('node:fs'), path = require('node:path'), net = require('node:net')
const { spawn } = require('node:child_process')
const assert = require('node:assert/strict')
const { chromium } = require(process.env.M2_PLAYWRIGHT || 'playwright')
const root = path.resolve(__dirname, '../..'), out = path.join(root, '.cache/m2-browser')
const captureMedia = process.env.M2_CAPTURE_MEDIA === '1'
fs.mkdirSync(out, { recursive: true })
const children = []
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
async function port() {
  const server = net.createServer(); await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const value = server.address().port; await new Promise(resolve => server.close(resolve)); return value
}
function start(command, args, env) {
  const child = spawn(command, args, { cwd: root, env: { ...process.env, ...env }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  let logs = ''; child.stdout.on('data', data => logs += data); child.stderr.on('data', data => logs += data)
  child.on('error', error => logs += error.message); child.logs = () => logs
  children.push(child); return child
}
async function ready(url, child) {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(url)).ok) return } catch {}
    if (child.exitCode !== null) throw new Error(child.logs())
    await pause(150)
  }
  throw new Error('Server unavailable: ' + child.logs())
}
async function until(fn, limit = 5000) {
  const start = performance.now()
  while (performance.now() - start < limit) { if (await fn()) return; await pause(50) }
  throw new Error('Condition timed out')
}
let browser, backendProcess
const networkFailures = []
;(async () => {
  const apiPort = await port(), webPort = await port()
  const api = `http://127.0.0.1:${apiPort}`, web = `http://127.0.0.1:${webPort}`
  const backend = start(process.env.M2_PYTHON || path.join(root, '.venv/Scripts/python.exe'), ['tests/browser/m2_server.py', String(apiPort)], { CORS_ALLOWED_ORIGINS: web })
  backendProcess = backend
  const front = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', String(webPort), '--strictPort'], { cwd: path.join(root, 'frontend'), env: { ...process.env, VITE_API_BASE_URL: api }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  let frontLogs = ''; front.stdout.on('data', data => frontLogs += data); front.stderr.on('data', data => frontLogs += data); front.logs = () => frontLogs; children.push(front)
  await Promise.all([ready(`${api}/api/health`, backend), ready(web, front)])
  browser = await chromium.launch({ headless: true, ...(process.env.M2_BROWSER_CHANNEL ? { channel: process.env.M2_BROWSER_CHANNEL } : {}) })
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, reducedMotion: 'reduce' })
  const page = await context.newPage(), errors = [], requests = []
  page.setDefaultTimeout(10000)
  page.on('pageerror', error => errors.push(error.message))
  page.on('requestfailed', request => { if (request.url().startsWith(api)) networkFailures.push({ url: request.url(), error: request.failure()?.errorText }) })
  page.on('request', request => { if (request.url().startsWith(api)) requests.push(request.url()) })
  await context.route('**/*', route => route.request().url().startsWith(web) || route.request().url().startsWith(api) ? route.continue() : route.abort())
  const call = async (p, body, protectedCall = false) => {
    const response = await fetch(api + p, { method: body === undefined ? 'GET' : 'POST', headers: { ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...(protectedCall ? { 'X-Review-Token': 'm2-isolated-test' } : {}) }, body: body === undefined ? undefined : JSON.stringify(body) })
    assert.ok(response.ok, `${p}: ${response.status} ${await response.clone().text()}`)
    return response.json()
  }
  await page.goto(web)
  await page.getByRole('button', { name: 'Find resilient routes' }).waitFor()
  await page.getByRole('combobox', { name: 'TO', exact: true }).click()
  await page.getByRole('option', { name: /Admiralty/ }).click()
  // Tomorrow's morning service stays after real publication regardless of the
  // runner time, and avoids midnight rollover/no-night-service false failures.
  const departureDate = new Date(Date.now() + 8 * 3600000 + 24 * 3600000).toISOString().slice(0, 10)
  await page.locator('[aria-controls="departure-calendar"]').click()
  const chosenDay = page.locator(`[data-date="${departureDate}"]`)
  if (!(await chosenDay.isVisible())) await page.getByRole('button', { name: 'Next month', exact: true }).click()
  await chosenDay.click()
  await page.getByLabel('Departure time HKT', { exact: true }).fill('08:20')
  await page.getByRole('button', { name: 'Find resilient routes' }).click()
  await page.getByRole('heading', { name: 'Tai Wai → Admiralty' }).waitFor()
  assert.ok(!(await page.locator('body').innerText()).includes('NaN'))
  // Public intake and manual first-card creation, through the actual UI.
  await page.getByRole('button', { name: 'Report', exact: true }).click()
  await page.getByLabel('What did you see?').fill('【模拟浏览器测试】东铁线红磡至会展信号故障，暂停服务。')
  await page.getByRole('button', { name: /Send unverified report/ }).click()
  await page.getByText('Report received — not yet verified.').waitFor()
  await page.getByRole('button', { name: 'Review', exact: true }).click()
  await page.getByLabel('Temporary credential').fill('m2-isolated-test')
  await page.getByRole('button', { name: 'Connect reviewer', exact: true }).click()
  await page.getByRole('button', { name: 'Extract / merge' }).click()
  await page.getByRole('heading', { name: 'Confirm extracted draft' }).waitFor()
  await page.getByRole('combobox', { name: /^Direction/ }).selectOption('both')
  await page.getByLabel('Severity (1–5)', { exact: true }).fill('4')
  await page.getByLabel('Confirmed capacity factor (0–1)').fill('0')
  await page.getByRole('button', { name: 'Create pending card' }).click()
  await page.getByText('Pending card created.', { exact: false }).waitFor()
  let events = await call('/api/events', undefined, true), event = events[0]
  assert.equal(event.confidence, .2)
  assert.deepEqual(await call('/api/events/published'), [])
  assert.deepEqual((await call('/api/graph/snapshot')).affected_edges, [])
  // Two explicitly scripted independent source references exercise confidence.
  for (const author of ['scripted-browser-2', 'scripted-browser-3']) {
    await call('/api/signals', { raw_text: '【模拟浏览器测试】东铁线红磡至会展信号故障，暂停服务。', author_hint: author })
    await page.getByRole('button', { name: 'Refresh reports' }).click()
    await page.getByRole('button', { name: 'Extract / merge' }).click()
    await page.getByText(/^Evidence merged using rule fallback\./).waitFor()
  }
  const reviewPath = `/api/events/${event.event_id}/review`
  await until(async () => (await call('/api/events', undefined, true))[0].confidence === .55)
  await page.getByRole('button', { name: 'Refresh events ↻' }).click()
  await page.getByRole('button', { name: 'Publish →', exact: true }).click()
  const approveResponse = page.waitForResponse(response => response.url().endsWith(reviewPath) && response.request().postDataJSON()?.action === 'approve')
  const routeResponse = page.waitForResponse(response => response.url().endsWith('/api/routes/query') && response.status() === 200)
  const started = performance.now()
  await page.getByRole('button', { name: 'Confirm publication' }).click()
  const approvedCard = await (await approveResponse).json()
  const updatedRoutes = await (await routeResponse).json()
  assert.ok(updatedRoutes.every(route => route.legs.every(leg => !(leg.line === 'ERL' && leg.from === 'HUH' && leg.to === 'EXC'))))
  await until(async () => (await call('/api/events/published')).length === 1)
  await page.locator(`[data-event-revisions*="${event.event_id}@${approvedCard.version}"]`).waitFor()
  const timings = [performance.now() - started]
  await page.getByRole('button', { name: 'Plan journey', exact: true }).click()
  await page.getByRole('button', { name: 'Find resilient routes' }).click()
  await page.getByRole('heading', { name: 'Tai Wai → Admiralty' }).waitFor()
  await page.waitForTimeout(600)
  if (captureMedia) await page.screenshot({ path: path.join(out, 'published-desktop.png'), fullPage: true })
  // Public visitors see impact even with no reviewer credential; changed facts
  // remain out of public maps until the next explicit approval.
  const visitor = await context.newPage()
  await visitor.goto(web)
  await visitor.getByRole('button', { name: 'Find resilient routes' }).waitFor()
  await visitor.getByRole('button', { name: 'Updates', exact: true }).click()
  await visitor.getByText(event.title, { exact: true }).first().waitFor()
  await visitor.getByRole('button', { name: 'Review', exact: true }).click()
  await visitor.getByLabel('Temporary credential').fill('deliberately-wrong-test')
  await visitor.getByRole('button', { name: 'Connect reviewer', exact: true }).click()
  await visitor.getByRole('alert').filter({ hasText: 'HTTP 401' }).waitFor()
  await visitor.getByRole('button', { name: 'Updates', exact: true }).click()
  await visitor.getByText(event.title, { exact: true }).first().waitFor()
  await call(reviewPath, { action: 'edit', actor: 'scripted-browser', edits: { title: 'Pending title stays private' } }, true)
  assert.equal((await call('/api/events/published'))[0].title, event.title)
  for (let run = 0; run < 2; run++) {
    const nextRoute = page.waitForResponse(response => response.url().endsWith('/api/routes/query') && response.ok())
    const begin = performance.now()
    const saved = await call(reviewPath, { action: 'approve', actor: 'scripted-browser' }, true)
    await nextRoute
    await page.locator(`[data-event-revisions*="${event.event_id}@${saved.version}"]`).waitFor()
    timings.push(performance.now() - begin)
    if (run === 0) await call(reviewPath, { action: 'edit', actor: 'scripted-browser', edits: { title: 'Approved third revision' } }, true)
  }
  assert.ok(timings.every(ms => ms <= 5000), JSON.stringify(timings))
  // A confirmed write followed by a failed refresh must not invite a retry.
  await page.getByRole('button', { name: 'Review', exact: true }).click()
  await page.getByRole('button', { name: 'Edit fields ↗' }).click()
  await page.getByLabel('Title', { exact: true }).fill('Confirmed write with blocked refresh')
  await page.route(`${api}/api/meta`, route => route.abort())
  const savedEdit = page.waitForResponse(response => response.url().endsWith(reviewPath) && response.request().postDataJSON()?.action === 'edit')
  await page.getByRole('button', { name: 'Save draft', exact: true }).click()
  assert.equal((await savedEdit).status(), 200)
  await page.getByText('Review saved by API · refreshing events and routes').waitFor()
  assert.equal((await call('/api/events', undefined, true))[0].title, 'Confirmed write with blocked refresh')
  assert.ok(!(await page.locator('body').innerText()).includes('The review could not be confirmed.'))
  await page.unroute(`${api}/api/meta`)
  // Disconnect the stream only: public polling must still update the map/cards.
  await page.getByRole('button', { name: 'Disconnect reviewer' }).click()
  const pollingStarted = performance.now()
  await call(reviewPath, { action: 'expire', actor: 'scripted-browser' }, true)
  await until(async () => (await call('/api/graph/snapshot')).affected_edges.length === 0)
  await page.locator('[data-event-revisions=""]').waitFor()
  const pollingWithdrawal = performance.now() - pollingStarted
  assert.ok(pollingWithdrawal <= 5000, `Polling withdrawal took ${pollingWithdrawal}ms`)
  await page.getByRole('button', { name: 'Plan journey', exact: true }).click()
  await page.getByRole('button', { name: 'Find resilient routes' }).click()
  await page.getByRole('heading', { name: 'Tai Wai → Admiralty' }).waitFor()
  // Offline retains existing route cards with an explicit stale notice.
  await context.setOffline(true)
  await page.getByText('Refresh failed; displayed data may be stale.', { exact: false }).waitFor({ timeout: 15000 })
  assert.ok(await page.getByRole('heading', { name: 'Tai Wai → Admiralty' }).isVisible())
  if (captureMedia) await page.screenshot({ path: path.join(out, 'offline-retained.png'), fullPage: true })
  await context.setOffline(false)
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await until(async () => !(await page.locator('body').innerText()).includes('Refresh failed; displayed data may be stale.'))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForTimeout(600)
  if (captureMedia) await page.screenshot({ path: path.join(out, 'mobile.png'), fullPage: true })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)
  assert.equal(overflow, false, 'Mobile horizontal overflow')
  assert.deepEqual(errors, [])
  assert.ok(requests.every(url => !url.includes('token=')))
  assert.equal(await page.evaluate(() => Object.keys(localStorage).length + Object.keys(sessionStorage).length), 0)
  fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify({ timings_ms: timings.map(Math.round), polling_withdrawal_ms: Math.round(pollingWithdrawal), errors, assertions: ['public-query', 'UI-report-draft-create', 'evidence-merge', 'UI-approve', 'public-without-auth', 'wrong-reviewer-public-isolation', 'approved-revision-isolation', 'three-refresh-timings', 'confirmed-write-refresh-failure', 'polling-withdrawal', 'offline-retention', 'recovery', 'mobile-overflow', 'no-token-url-or-storage'] }, null, 2))
  console.log(JSON.stringify({ passed: true, timings_ms: timings.map(Math.round), polling_withdrawal_ms: Math.round(pollingWithdrawal), artifacts: out }))
})().catch(async error => {
  console.error(error.stack)
  console.error(JSON.stringify(networkFailures))
  fs.writeFileSync(path.join(out, 'server.log'), backendProcess?.logs() ?? '')
  if (browser) { const pages = browser.contexts().flatMap(context => context.pages()); for (let i = 0; i < pages.length; i++) { if (captureMedia) await pages[i].screenshot({ path: path.join(out, `failure-${i}.png`), fullPage: true }).catch(() => {}); fs.writeFileSync(path.join(out, `failure-${i}.txt`), await pages[i].locator('body').innerText().catch(() => '')) } }
  process.exitCode = 1
}).finally(async () => {
  await browser?.close()
  for (const child of children) if (child.exitCode === null) {
    if (process.platform === 'win32') await new Promise(resolve => spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }).on('exit', resolve))
    else child.kill('SIGTERM')
  }
})
