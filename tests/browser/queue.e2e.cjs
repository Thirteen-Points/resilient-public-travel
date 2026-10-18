// Verify queue estimates through the real backend, route cards and detail page.
const fs = require('node:fs'), path = require('node:path'), net = require('node:net')
const { spawn } = require('node:child_process'), assert = require('node:assert/strict')
const { chromium } = require(process.env.M2_PLAYWRIGHT || 'playwright')
const root = path.resolve(__dirname, '../..'), out = path.join(root, '.cache/queue-browser')
fs.mkdirSync(out, { recursive: true })
const demandPath = path.join(out, 'demand.txt'), children = []
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
async function port() {
  const server = net.createServer()
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const value = server.address().port
  await new Promise(resolve => server.close(resolve))
  return value
}
function start(command, args, cwd, env) {
  const child = spawn(command, args, { cwd, env: { ...process.env, ...env }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  let logs = ''
  child.stdout.on('data', data => logs += data); child.stderr.on('data', data => logs += data)
  child.on('error', error => logs += error.message); child.logs = () => logs; children.push(child)
  return child
}
async function ready(url, child) {
  for (let i = 0; i < 200; i++) {
    try { if ((await fetch(url)).ok) return } catch {}
    if (child.exitCode !== null) throw new Error(child.logs())
    await pause(150)
  }
  throw new Error('Server unavailable: ' + child.logs())
}
const formatRange = range => `${Math.round(range[0] / 60)}–${Math.round(range[1] / 60)} min`
let browser
;(async () => {
  fs.writeFileSync(demandPath, '0')
  const api = `http://127.0.0.1:${await port()}`, web = `http://127.0.0.1:${await port()}`
  const backend = start(process.env.M2_PYTHON || path.join(root, '.venv/Scripts/python.exe'),
    ['tests/browser/queue_server.py', api.split(':').at(-1), demandPath], root, { CORS_ALLOWED_ORIGINS: web })
  const front = start(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', web.split(':').at(-1), '--strictPort'],
    path.join(root, 'frontend'), { VITE_API_BASE_URL: api })
  await Promise.all([ready(api + '/api/health', backend), ready(web, front)])
  browser = await chromium.launch({ headless: true, ...(process.env.M2_BROWSER_CHANNEL ? { channel: process.env.M2_BROWSER_CHANNEL } : process.platform === 'win32' ? { channel: 'msedge' } : {}) })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
  page.setDefaultTimeout(20000)
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(web + '?view=planner')
  await page.getByRole('combobox', { name: 'TO', exact: true }).click()
  await page.getByRole('option', { name: /^Admiralty East Rail/ }).click()
  const routeResponse = () => page.waitForResponse(response => response.url() === api + '/api/routes/query' && response.request().method() === 'POST')
  let pending = routeResponse()
  await page.getByRole('button', { name: /Find.*route|Plan.*route/i }).click()
  const baseline = await (await pending).json()
  assert.ok(baseline.length > 0)
  await page.locator('[data-route-id] [data-queue-delay="0"]').first().waitFor()
  fs.writeFileSync(demandPath, '1000000')
  await page.getByRole('button', { name: 'Edit journey', exact: false }).click()
  pending = routeResponse()
  await page.getByRole('button', { name: /Find.*route|Plan.*route/i }).click()
  const loaded = await (await pending).json(), old = new Map(baseline.map(route => [route.route_id, route]))
  for (const route of loaded) {
    const before = old.get(route.route_id)
    assert.ok(before)
    const delay = route.total.queue_delay_s
    assert.ok(delay > 0)
    for (let i = 0; i < 2; i++) assert.ok(Math.abs(route.total.time_range_s[i] - before.total.time_range_s[i] - delay) < 1e-6)
    const card = page.locator(`[data-route-id="${route.route_id}"]`)
    await card.locator(`[data-queue-delay="${delay}"]`).waitFor()
    assert.ok((await card.innerText()).includes(formatRange(route.total.time_range_s)))
    assert.ok((await card.innerText()).includes(`Includes ${(delay / 60).toFixed(1)} min extra queueing`))
  }
  await page.screenshot({ path: path.join(out, 'queue-results.png'), fullPage: true })
  const selected = loaded[0]
  await page.locator(`[data-route-id="${selected.route_id}"]`).getByRole('button', { name: 'View steps' }).click()
  await page.getByRole('heading', { name: 'Step by step', exact: true }).waitFor()
  assert.ok((await page.locator('main').innerText()).includes(formatRange(selected.total.time_range_s)))
  await page.locator(`[data-queue-delay="${selected.total.queue_delay_s}"]`).waitFor()
  await page.screenshot({ path: path.join(out, 'queue-detail.png'), fullPage: true })
  assert.deepEqual(errors, [])
  const report = { passed: true, demand: 'explicit simulated people/hour', routes: loaded.map(route => ({
    route_id: route.route_id, before_range_s: old.get(route.route_id).total.time_range_s,
    queue_delay_s: route.total.queue_delay_s, after_range_s: route.total.time_range_s,
  })), assertions: ['real-API-demand-change', 'both-range-bounds-shift', 'route-card-ETA', 'queue-inclusion-label', 'detail-ETA', 'no-browser-errors'] }
  fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
})().catch(error => { console.error(error); process.exitCode = 1 }).finally(async () => {
  if (browser) await browser.close()
  for (const child of children) child.kill()
})
