// Real backend integration and explicitly injected failure cases. No media is
// recorded and no delivery/report artifacts are created by this regression.
const path = require('node:path'), net = require('node:net')
const { spawn } = require('node:child_process')
const assert = require('node:assert/strict')
const { chromium } = require(process.env.M2_PLAYWRIGHT || 'playwright')
const { publication, until, frames, mapPainted } = require('./p3-render-timing.cjs')
const { navigate, signInAdministrator, assertRemovedPages } = require('./public-ui.cjs')
const root = path.resolve(__dirname, '../..'), children = [], errors = [], checks = []
const normalId = 'm2_six_station_directed_od_am_peak_p3_shared_segments'
const stressId = normalId + '_residual_10pct'
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
async function port() {
  const server = net.createServer(); await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const result = server.address().port; await new Promise(resolve => server.close(resolve)); return result
}
function start(command, args, env, cwd = root) {
  const child = spawn(command, args, { cwd, env: { ...process.env, ...env }, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  let log = ''; child.stdout.on('data', data => log += data); child.stderr.on('data', data => log += data); child.on('error', error => log += error.message)
  child.logs = () => log; children.push(child); return child
}
async function ready(url, child) {
  for (let i = 0; i < 120; i++) {
    try { if ((await fetch(url)).ok) return } catch {}
    if (child.exitCode !== null) throw new Error(child.logs())
    await pause(150)
  }
  throw new Error('Server unavailable: ' + child.logs())
}
function pass(name) { checks.push(name); console.log('PASS ' + name) }
async function selectStation(page, field, name) {
  await page.getByRole('combobox', { name: field, exact: true }).click()
  await page.getByRole('option', { name: new RegExp(`^${name} East Rail ·`) }).click()
}
async function chooseTomorrow(page) {
  const day = new Date(Date.now() + 8 * 3600000 + 24 * 3600000).toISOString().slice(0, 10)
  await page.locator('[aria-controls="departure-calendar"]').click()
  const chosen = page.locator(`[data-date="${day}"]`)
  if (!await chosen.isVisible()) await page.getByRole('button', { name: 'Next month', exact: true }).click()
  await chosen.click(); await page.getByLabel('Departure time HKT', { exact: true }).fill('08:20')
  return `${day}T08:20:00+08:00`
}
async function noOverflow(page, label) {
  await frames(page)
  const layout = await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth,
    panels: Array.from(document.querySelectorAll('[data-panel]')).filter(el => el.getBoundingClientRect().width > 0).map(el => ({ left: el.getBoundingClientRect().left, right: el.getBoundingClientRect().right })) }))
  assert.ok(layout.document <= layout.width + 1, `${label}: document overflow ${JSON.stringify(layout)}`)
  assert.ok(layout.panels.every(panel => panel.left >= -1 && panel.right <= layout.width + 1), `${label}: panel outside viewport ${JSON.stringify(layout)}`)
}
let browser, publicPage
;(async () => {
  const api = `http://127.0.0.1:${await port()}`, web = `http://127.0.0.1:${await port()}`
  const backend = start(process.env.M2_PYTHON || path.join(root, '.venv/Scripts/python.exe'), ['tests/browser/m2_server.py', new URL(api).port], { CORS_ALLOWED_ORIGINS: web })
  const front = start(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', new URL(web).port, '--strictPort'], { VITE_API_BASE_URL: api }, path.join(root, 'frontend'))
  await Promise.all([ready(api + '/api/health', backend), ready(web, front)])
  const call = async (endpoint, body, protectedCall = false) => {
    const response = await fetch(api + endpoint, { method: body === undefined ? 'GET' : 'POST', headers: { ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...(protectedCall ? { 'X-Review-Token': 'm2-isolated-test' } : {}) }, body: body === undefined ? undefined : JSON.stringify(body) })
    assert.ok(response.ok, `${endpoint}: ${response.status} ${await response.clone().text()}`); return response.json()
  }
  browser = await chromium.launch({ headless: true, ...(process.env.M2_BROWSER_CHANNEL ? { channel: process.env.M2_BROWSER_CHANNEL } : {}) })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
  await context.route('**/*', route => route.request().url().startsWith(web) || route.request().url().startsWith(api) ? route.continue() : route.abort())
  await context.route('https://valhalla1.openstreetmap.de/route', route => route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify({ trip: { summary: { length: 0.2 } } }) }))
  const page = await context.newPage(); publicPage = page; page.setDefaultTimeout(15000)
  page.on('pageerror', error => errors.push(error.message))
  const routeBodies = [], chatBodies = [], preferenceBodies = [], forbiddenHeaders = []
  page.on('request', request => {
    if (request.url().startsWith(api) && (request.headers()['x-review-token'] || request.headers()['x-csrf-token'] || request.headers().authorization)) forbiddenHeaders.push(new URL(request.url()).pathname)
    if (request.url() === api + '/api/routes/query') routeBodies.push(request.postDataJSON())
    if (request.url() === api + '/api/ai/chat') chatBodies.push(request.postDataJSON())
    if (request.url() === api + '/api/persona/parse') preferenceBodies.push(request.postDataJSON())
  })
  await page.goto(web); await page.getByRole('button', { name: 'Find resilient routes' }).waitFor()
  await assertRemovedPages(page)
  await selectStation(page, 'TO', 'Admiralty'); const departAt = await chooseTomorrow(page)
  // All 30 directed station pairs exercise the actual engine for both profiles.
  const stations = ['TAW', 'KOT', 'MKK', 'HUH', 'EXC', 'ADM']
  for (const origin of stations) for (const destination of stations.filter(id => id !== origin)) for (const mobility of ['standard', 'wheelchair']) {
    const profile = mobility === 'standard' ? { mobility, preset: 'fastest', hard_flags: [] } : { mobility, preset: 'most_stable', max_walk_m: 400, max_transfers: 2, hard_flags: ['no_stairs', 'no_minibus', 'no_non_lowfloor_bus'] }
    const routes = await call('/api/routes/query', { origin, destination, depart_at: departAt, profile })
    assert.ok(Array.isArray(routes))
    for (const route of routes) {
      assert.ok(Number.isFinite(route.score) && Number.isFinite(route.total.time_s))
      assert.equal(route.legs[0].from, origin); assert.equal(route.legs.at(-1).to, destination)
      assert.ok(route.legs.every(leg => Number.isFinite(leg.fare_hkd) && leg.fare_hkd >= 0))
      assert.ok(Math.abs(route.legs.reduce((sum, leg) => sum + leg.fare_hkd, 0) - route.total.fare_hkd) < 0.005, 'Each ticket charge must reconcile with the displayed journey fare')
      if (mobility === 'wheelchair') assert.ok(route.total.walk_m <= 400 && route.total.transfers <= 2 && route.legs.every(leg => leg.accessible === true && leg.mode !== 'MINIBUS'))
    }
  }
  pass('real engine: 30 directed OD pairs × 2 profiles')
  // Actual preference extraction, explicit preview, then a real new route query.
  const text = page.getByLabel('Travel preferences', { exact: true })
  await text.fill('我坐轮椅，少走路，越便宜越好')
  const personaReply = page.waitForResponse(response => response.url() === api + '/api/persona/parse' && response.ok())
  await page.getByRole('button', { name: 'Preview preferences' }).click()
  const actualPreference = await (await personaReply).json()
  await page.locator('[data-preference-preview]').waitFor()
  assert.ok((await page.locator('[data-preference-preview]').innerText()).includes(actualPreference.explanation))
  assert.equal(routeBodies.length, 0, 'Preview must not change routing')
  assert.equal(preferenceBodies[0].current_profile.mobility, 'standard')
  const routeReply = page.waitForResponse(response => response.url() === api + '/api/routes/query' && response.ok())
  await page.getByRole('button', { name: 'Apply preferences', exact: true }).click()
  const actualRoutes = await (await routeReply).json()
  await page.getByRole('heading', { name: 'Tai Wai → Admiralty' }).waitFor()
  const applied = routeBodies[0].profile
  assert.equal(applied.mobility, 'wheelchair'); assert.ok(applied.max_walk_m <= 400)
  assert.ok(applied.hard_flags.includes('no_stairs') && applied.hard_flags.includes('no_minibus'))
  assert.deepEqual(await page.locator('[data-route-id]').evaluateAll(elements => elements.map(el => el.getAttribute('data-route-id'))), actualRoutes.map(route => route.route_id))
  for (const route of actualRoutes) assert.ok((await page.locator(`[data-route-id="${route.route_id}"]`).innerText()).includes(`HK$${route.total.fare_hkd.toFixed(2)}`))
  pass('real preferences: preview, confirmation, accessible routing')
  await navigate(page, 'Agent')
  const actualChatResponse = page.waitForResponse(response => response.url() === api + '/api/ai/chat' && response.ok())
  await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').fill('Explain the returned route estimates')
  await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').press('Enter')
  const actualChat = await (await actualChatResponse).json()
  await until(async () => (await page.getByRole('log').innerText()).includes(actualChat.message))
  assert.deepEqual(chatBodies[0].profile, applied)
  assert.equal(chatBodies[0].depart_at, departAt)
  assert.ok((await page.getByRole('log').innerText()).includes(actualChat.fallback ? 'BACKEND FALLBACK' : 'BACKEND ANSWER'))
  if (!actualChat.effective_profile) await page.getByText('Effective-profile metadata not supplied.', { exact: false }).waitFor()
  pass('real chat: same confirmed profile, actual answer and fallback metadata')
  // Failure injection: previous answer survives HTTP errors and ignored abort.
  await page.route(api + '/api/ai/chat', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Injected P4 failure' }) }))
  await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').fill('test unavailable'); await page.getByRole('button', { name: 'Send message', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: 'Injected P4 failure' }).waitFor()
  assert.ok((await page.getByRole('log').innerText()).includes(actualChat.message))
  await page.unroute(api + '/api/ai/chat')
  let releaseChat
  await page.route(api + '/api/ai/chat', async route => { await new Promise(resolve => releaseChat = resolve); await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...actualChat, message: 'OBSOLETE P4 ANSWER' }) }).catch(() => {}) })
  await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').fill('test cancellation'); await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').press('Enter')
  await page.getByRole('button', { name: 'Cancel reply', exact: true }).waitFor(); await until(() => Boolean(releaseChat))
  await page.getByRole('button', { name: 'Cancel reply', exact: true }).click(); releaseChat(); await frames(page)
  assert.ok(!(await page.getByRole('log').innerText()).includes('OBSOLETE P4 ANSWER'))
  await page.unroute(api + '/api/ai/chat'); pass('injected chat failure and cancelled stale completion')
  // Context changes invalidate a persona preview before it can be applied.
  await navigate(page, 'Plan journey')
  await text.fill('便宜一点'); await page.getByRole('button', { name: 'Preview preferences' }).click(); await page.locator('[data-preference-preview]').waitFor()
  await page.getByRole('button', { name: 'Commuter', exact: true }).click()
  assert.ok(await page.getByRole('button', { name: 'Apply preferences', exact: true }).isDisabled())
  await page.route(api + '/api/persona/parse', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ method: 'rule_fallback', explanation: 'Injected malformed preference', patch: { hard_flags: ['ignore_accessibility'] } }) }))
  await text.fill('Injected malformed preferences'); await page.getByRole('button', { name: 'Preview preferences' }).click()
  await page.getByRole('alert').filter({ hasText: 'Invalid preference patch' }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Commuter', exact: true }).getAttribute('aria-pressed'), 'true')
  await page.unroute(api + '/api/persona/parse')
  let releasePreference
  await page.route(api + '/api/persona/parse', async route => { await new Promise(resolve => releasePreference = resolve); await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(actualPreference) }).catch(() => {}) })
  await text.fill('Injected slow preference request'); await page.getByRole('button', { name: 'Preview preferences' }).click(); await until(() => Boolean(releasePreference))
  await page.getByRole('button', { name: 'Cancel preferences', exact: true }).click(); releasePreference(); await page.unroute(api + '/api/persona/parse'); await frames(page)
  assert.equal(await page.locator('[data-preference-preview]').count(), 0)
  await text.fill('我坐轮椅'); await page.getByRole('button', { name: 'Preview preferences' }).click(); await page.locator('[data-preference-preview]').waitFor()
  assert.ok((await page.locator('[data-preference-preview]').innerText()).includes('Wheelchair'))
  pass('context changes, malformed preference patches and cancelled previews retain settings')
  // Cancel a route query by selecting a different destination before response.
  let releaseRoutes
  await page.route(api + '/api/routes/query', async route => { await new Promise(resolve => releaseRoutes = resolve); await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(actualRoutes) }).catch(() => {}) })
  await page.getByRole('button', { name: 'Find resilient routes' }).click(); await until(() => Boolean(releaseRoutes))
  await selectStation(page, 'TO', 'Hung Hom'); releaseRoutes(); await page.unroute(api + '/api/routes/query')
  await page.getByRole('button', { name: 'Find resilient routes' }).waitFor(); assert.equal(await page.locator('#routes-heading').count(), 0)
  releaseRoutes = undefined
  await page.route(api + '/api/routes/query', async route => { await new Promise(resolve => releaseRoutes = resolve); await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(actualRoutes) }).catch(() => {}) })
  await page.getByRole('button', { name: 'Find resilient routes' }).click(); await until(() => Boolean(releaseRoutes))
  await navigate(page, 'How it works'); releaseRoutes(); await page.unroute(api + '/api/routes/query'); await frames(page)
  assert.ok(await page.getByRole('heading', { name: 'Source freshness & collection', exact: true }).isVisible())
  assert.equal(await page.locator('#routes-heading').count(), 0)
  await navigate(page, 'Plan journey')
  await page.getByRole('button', { name: 'Find resilient routes' }).click(); await page.getByRole('heading', { name: 'Tai Wai → Hung Hom' }).waitFor()
  pass('changing stations or leaving the planner cancels obsolete route navigation')
  // Removed presentation pages retain their backend API contracts.
  const pair = await Promise.all(['standard', 'wheelchair'].map(mobility => call('/api/routes/query', {
    origin: 'TAW', destination: 'ADM', depart_at: departAt, event_ids: [],
    profile: mobility === 'standard' ? { mobility, preset: 'fastest', hard_flags: [] }
      : { mobility, preset: 'most_stable', max_walk_m: 400, max_transfers: 2, hard_flags: ['no_stairs', 'no_minibus', 'no_non_lowfloor_bus'] },
  })))
  assert.ok(pair.every(routes => Array.isArray(routes) && routes.length > 0))
  const normal = await call(`/api/sim/result?scenario_id=${normalId}`)
  const stress = await call(`/api/sim/result?scenario_id=${stressId}`)
  assert.ok(normal.generated_at && normal.query_time && stress.generated_at && stress.query_time)
  assert.equal(normal.baseline.total_delay_person_min, normal.guided.total_delay_person_min)
  assert.equal(stress.guided.unassigned_demand, 199)
  assert.ok(stress.guided.total_delay_person_min < stress.baseline.total_delay_person_min)
  assert.ok(stress.guided.resource_load.length > 0)
  const missing = await fetch(api + '/api/sim/result?scenario_id=missing-browser-test-scenario')
  assert.equal(missing.status, 404)
  pass('comparison profiles and simulation contracts remain available through the API')
  // Latest mode selection includes connecting modes and displays every result.
  await navigate(page, 'Plan journey'); await page.getByRole('button', { name: 'Commuter', exact: true }).click()
  await selectStation(page, 'TO', 'Admiralty')
  for (const [label, mode] of [['Bus · 公交', 'BUS'], ['Ferry · 渡轮', 'FERRY']]) {
    await page.getByRole('button', { name: label, exact: true }).click()
    const reply = page.waitForResponse(response => response.url().endsWith('/api/routes/query') && response.ok() && response.request().postDataJSON()?.required_modes?.[0] === mode)
    await page.getByRole('button', { name: 'Find resilient routes' }).click()
    const candidates = await (await reply).json()
    assert.ok(candidates.length > 0 && candidates.every(route => route.legs.some(leg => leg.mode === mode)), `${mode}: every journey must include the selected mode`)
    await page.locator('#routes-heading').waitFor()
    assert.deepEqual(await page.locator('[data-route-id]').evaluateAll(elements => elements.map(element => element.dataset.routeId)), candidates.map(route => route.route_id))
    if (candidates.length > 3) {
      const later = page.locator('[data-route-id]').nth(3)
      await later.getByRole('button').first().click()
      assert.equal(await later.getByRole('button').first().getAttribute('aria-pressed'), 'true')
      await page.getByRole('button', { name: 'View steps →', exact: true }).nth(3).click()
      await page.getByText('Each ticket is shown on its first step;', { exact: false }).waitFor()
    }
    await navigate(page, 'Plan journey')
  }
  await page.getByRole('button', { name: 'Minibus · 小巴', exact: true }).click()
  await page.getByText('Minibus · 小巴: routes are not available in this modelled network yet.', { exact: false }).waitFor()
  await page.getByRole('button', { name: 'Find resilient routes' }).click(); await page.locator('#routes-heading').waitFor()
  assert.equal(await page.locator('[data-route-id]').count(), 0)
  await page.getByText('Minibus routes are not available in the current modelled network yet.', { exact: false }).waitFor()
  await navigate(page, 'Plan journey'); await page.getByRole('button', { name: 'All modes', exact: true }).click()
  await selectStation(page, 'TO', 'Hung Hom'); await page.getByRole('button', { name: 'Find resilient routes' }).click(); await page.locator('#routes-heading').waitFor()
  pass('bus/ferry mode inclusion, all returned alternatives, later-route selection and explicit unavailable minibus')
  // Source failure is isolated from route queries and preserves previous status.
  await navigate(page, 'How it works'); await page.locator('[data-source="mtr"]').waitFor()
  const actualSources = await call('/api/sources/status'); assert.equal(actualSources.publishes_events, false)
  if (!actualSources.sources.mtr.last_success_at) await page.getByText('No persistent last-success time supplied.', { exact: false }).first().waitFor()
  await page.route(api + '/api/sources/status', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Injected collection failure' }) }))
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: 'Collection status refresh failed' }).waitFor()
  assert.ok(await page.locator('[data-source="mtr"]').isVisible())
  await navigate(page, 'Plan journey'); await page.getByRole('button', { name: 'Find resilient routes' }).click(); await page.getByRole('heading', { name: 'Tai Wai → Hung Hom' }).waitFor()
  await page.unroute(api + '/api/sources/status'); pass('actual source status and isolated collection failure')
  // Public polling is quiet while healthy and retains route cards offline.
  await assertRemovedPages(page)
  const previousRoutes = await page.locator('[data-route-id]').evaluateAll(elements => elements.map(element => element.dataset.routeId))
  await context.setOffline(true)
  await page.getByRole('alert').filter({ hasText: /Offline|Refresh failed/ }).waitFor()
  assert.deepEqual(await page.locator('[data-route-id]').evaluateAll(elements => elements.map(element => element.dataset.routeId)), previousRoutes)
  await context.setOffline(false)
  await page.getByRole('alert').filter({ hasText: /Offline|Refresh failed/ }).waitFor({ state: 'hidden' })
  await page.getByRole('status').filter({ hasText: 'Routes updated for the latest network.' }).waitFor()
  await page.getByRole('status').filter({ hasText: 'Routes updated for the latest network.' }).waitFor({ state: 'hidden', timeout: 6500 })
  // An explicit failed graph refresh exposes a retry; success removes it.
  await page.route(api + '/api/graph/snapshot**', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Injected graph refresh failure' }) }))
  const graphWarning = page.getByRole('alert').filter({ hasText: 'Refresh failed;' })
  await graphWarning.waitFor({ timeout: 15000 })
  await page.unroute(api + '/api/graph/snapshot**')
  await graphWarning.getByRole('button', { name: 'Refresh', exact: true }).click()
  await graphWarning.waitFor({ state: 'hidden' })
  pass('quiet healthy polling, offline retention, automatic recovery, retry and 4.2-second toast dismissal')
  // Actual collapsed menus and map/list panels, enlarged text and focus.
  for (const width of [1440, 1024, 800, 390, 320]) {
    await page.setViewportSize({ width, height: 900 })
    await navigate(page, 'Plan journey'); await noOverflow(page, `planner ${width}`)
    if (width < 1024) {
      for (const label of ['Bus · 公交', 'Ferry · 渡轮']) {
        const bounds = await page.getByRole('button', { name: label, exact: true }).boundingBox()
        assert.ok(bounds && bounds.y >= 0 && bounds.y + bounds.height <= 900, `${label}: selector is outside the first mobile screen`)
      }
      assert.equal(await page.locator('#main-navigation').isVisible(), false)
      const open = page.locator('#navigation-toggle')
      await open.click(); assert.equal(await open.getAttribute('aria-expanded'), 'true')
      await page.keyboard.press('Escape'); assert.equal(await page.locator('#main-navigation').isVisible(), false)
      assert.ok(await open.evaluate(button => button === document.activeElement))
      const content = page.locator('#journey-content'), map = page.locator('#journey-map')
      assert.equal(await content.isVisible(), true); assert.equal(await map.isVisible(), false)
      await page.getByRole('tab', { name: 'Journey', exact: true }).focus()
      await page.keyboard.press('ArrowRight')
      assert.equal(await map.isVisible(), true); assert.equal(await content.isVisible(), false)
      assert.equal(await page.getByRole('tab', { name: 'Map', exact: true }).getAttribute('aria-selected'), 'true')
      await page.keyboard.press('ArrowLeft')
      assert.equal(await content.isVisible(), true); assert.equal(await map.isVisible(), false)
    } else {
      assert.equal(await page.locator('#journey-map').isVisible(), true)
      assert.equal(await page.getByRole('tablist', { name: 'Journey view' }).count(), 0)
    }
    await page.getByRole('button', { name: 'Large text', exact: true }).click(); await page.getByRole('button', { name: 'High contrast', exact: true }).click(); await noOverflow(page, `planner large text ${width}`)
    await page.getByRole('button', { name: 'Large text', exact: true }).click(); await page.getByRole('button', { name: 'High contrast', exact: true }).click()
    await page.getByRole('button', { name: 'Find resilient routes' }).click(); await page.locator('#routes-heading').waitFor(); await noOverflow(page, `routes ${width}`)
    if (width < 1024) {
      const heading = await page.locator('#routes-heading').boundingBox()
      assert.ok(heading && heading.y >= 0 && heading.y + heading.height <= 900, `routes ${width}: heading inherits planner scroll position`)
      await page.getByRole('tab', { name: 'Map', exact: true }).click()
      assert.equal(await page.locator('#journey-content').isVisible(), false); await noOverflow(page, `route map ${width}`)
      await page.getByRole('tab', { name: 'Routes', exact: true }).click()
      assert.equal(await page.locator('#journey-map').isVisible(), false)
    }
    await page.getByRole('button', { name: 'View steps →', exact: true }).first().click(); await noOverflow(page, `steps ${width}`)
    if (width < 1024) {
      await page.getByRole('tab', { name: 'Map', exact: true }).click(); assert.equal(await page.locator('#journey-content').isVisible(), false)
      await page.getByRole('tab', { name: 'Steps', exact: true }).click(); assert.equal(await page.locator('#journey-map').isVisible(), false)
    }
    for (const name of ['Updates', 'Report', 'How it works', 'Agent']) { await navigate(page, name); await noOverflow(page, `${name} ${width}`) }
    const prompt = page.getByLabel('ASK ABOUT THE CURRENT JOURNEY'); await prompt.fill('Keyboard focus check'); await prompt.press('Tab')
    assert.ok(await page.getByRole('button', { name: 'Send message', exact: true }).evaluate(button => button === document.activeElement && getComputedStyle(button).outlineStyle !== 'none'))
  }
  // Map picking checks a pedestrian route to East Rail and returns to the form.
  await navigate(page, 'Plan journey'); await page.getByRole('button', { name: '◎ Tap the map', exact: true }).click()
  await page.locator('#journey-map').scrollIntoViewIfNeeded()
  await page.getByRole('button', { name: 'Fit corridor on map', exact: true }).click()
  await frames(page)
  let stationPoint
  await until(async () => {
    const label = await page.locator('#journey-map .leaflet-tooltip').filter({ hasText: 'Admiralty' }).first().boundingBox()
    if (!label) return false
    stationPoint = { x: label.x + label.width + 10, y: label.y + label.height / 2 }
    return page.evaluate(point => Boolean(document.elementFromPoint(point.x, point.y)?.closest('.leaflet-container')), stationPoint)
  }, 5000)
  await page.mouse.click(stationPoint.x, stationPoint.y)
  await page.locator('#journey-content').waitFor({ state: 'visible' })
  assert.equal(await page.locator('#journey-map').isVisible(), false)
  assert.match(await page.getByRole('combobox', { name: 'TO', exact: true }).inputValue(), /Admiralty/)
  pass('320–1440 px layouts, collapsed navigation, real map/list hiding, keyboard tabs and map picking')
  // A fresh compact page starts with a genuinely hidden map. First reveal and
  // subsequent resizes must paint without Leaflet/MapLibre lifecycle errors.
  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' })
  await mobileContext.route('**/*', route => route.request().url().startsWith(web) || route.request().url().startsWith(api) ? route.continue() : route.abort())
  const mobile = await mobileContext.newPage()
  mobile.on('pageerror', error => errors.push(error.message))
  mobile.on('request', request => {
    if (request.url().startsWith(api) && (request.headers()['x-review-token'] || request.headers()['x-csrf-token'] || request.headers().authorization)) forbiddenHeaders.push(new URL(request.url()).pathname)
  })
  await mobile.goto(web); await mobile.getByRole('button', { name: 'Find resilient routes' }).waitFor()
  assert.equal(await mobile.locator('#journey-map').isVisible(), false)
  await mobile.getByRole('tab', { name: 'Map', exact: true }).click()
  await mobile.locator('#journey-map').waitFor({ state: 'visible' })
  await until(async () => await mobile.locator('.leaflet-overlay-pane').count() > 0 && await mapPainted(mobile))
  for (const width of [320, 1440, 390]) {
    await mobile.setViewportSize({ width, height: 844 })
    await mobile.locator('#journey-map').waitFor({ state: 'visible' })
    await noOverflow(mobile, `fresh mobile map resized to ${width}`)
    await until(() => mapPainted(mobile))
  }
  await mobile.getByRole('tab', { name: 'Journey', exact: true }).click()
  assert.equal(await mobile.locator('#journey-map').isVisible(), false)
  await mobile.getByRole('tab', { name: 'Map', exact: true }).click()
  await until(() => mapPainted(mobile)); await frames(mobile)
  assert.deepEqual(errors, [])
  await mobileContext.close()
  pass('fresh mobile hidden-map reveal, repeated visibility changes and desktop/mobile resizes without browser errors')
  // Three real approvals, each measured after map and route-card rendering.
  await page.setViewportSize({ width: 1440, height: 1000 }); await navigate(page, 'Plan journey')
  await page.getByRole('button', { name: 'Commuter', exact: true }).click(); await selectStation(page, 'TO', 'Admiralty'); await page.getByRole('button', { name: 'Find resilient routes' }).click(); await page.getByRole('heading', { name: 'Tai Wai → Admiralty' }).waitFor()
  const reviewContext = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
  await reviewContext.route('**/*', route => route.request().url().startsWith(web) || route.request().url().startsWith(api) ? route.continue() : route.abort())
  const reviewer = await reviewContext.newPage(); reviewer.on('pageerror', error => errors.push(error.message))
  await navigate(page, 'Report'); await page.getByLabel('What did you see?').fill('【模拟 P4 浏览器测试】东铁线红磡至会展信号故障，暂停服务。')
  await page.getByRole('button', { name: /Send unverified report/ }).click(); await page.getByText('Report received — not yet verified.').waitFor()
  await navigate(page, 'Plan journey'); await page.getByRole('button', { name: 'Find resilient routes' }).click(); await page.locator('#routes-heading').waitFor()
  await signInAdministrator(reviewer, api)
  await reviewer.getByRole('button', { name: 'Extract / merge', exact: true }).click(); await reviewer.getByRole('combobox', { name: /^Direction/ }).selectOption('both')
  const hktInput = value => new Date(value + 8 * 3600000).toISOString().slice(0, 16)
  await reviewer.getByLabel('Start · HKT', { exact: true }).fill(hktInput(Date.now() - 5 * 60000))
  await reviewer.getByLabel('End · HKT', { exact: true }).fill(hktInput(Date.parse(departAt) + 30 * 60000))
  await reviewer.getByLabel('Severity (1–5)', { exact: true }).fill('4'); await reviewer.getByLabel('Confirmed capacity factor (0–1)').fill('0')
  await reviewer.getByRole('button', { name: 'Create pending card', exact: true }).click(); await reviewer.getByText('Pending card created.', { exact: false }).waitFor()
  const event = (await call('/api/events', undefined, true))[0]
  for (const author of ['p4-scripted-source-2', 'p4-scripted-source-3']) {
    await call('/api/signals', { raw_text: '【模拟 P4 浏览器测试】东铁线红磡至会展信号故障，暂停服务。', author_hint: author })
    await reviewer.getByRole('button', { name: 'Refresh reports', exact: true }).click(); await reviewer.getByRole('button', { name: 'Extract / merge', exact: true }).click(); await reviewer.getByText(/^Evidence merged using rule fallback\./).waitFor()
  }
  const timings = []
  for (let round = 0; round < 3; round++) {
    if (round) {
      const approvedTitle = (await call('/api/events/published'))[0].title
      const approvedRevision = await page.locator('[data-event-revisions]').getAttribute('data-event-revisions')
      await call(`/api/events/${event.event_id}/review`, { action: 'edit', actor: 'P4-test', edits: { title: `【模拟 P4 浏览器测试】revision ${round + 1}` } }, true)
      assert.equal((await call('/api/events/published'))[0].title, approvedTitle)
      await page.waitForResponse(response => response.url().includes('/api/events/published') && response.ok())
      await frames(page)
      assert.equal(await page.locator('[data-event-revisions]').getAttribute('data-event-revisions'), approvedRevision)
      assert.ok(!(await page.locator('#journey-content').innerText()).includes(`【模拟 P4 浏览器测试】revision ${round + 1}`))
    } else assert.deepEqual(await call('/api/events/published'), [])
    await reviewer.getByRole('button', { name: 'Refresh events ↻', exact: true }).click(); await reviewer.getByRole('button', { name: 'Publish →', exact: true }).click()
    const timing = await publication(page, reviewer, event.event_id); timings.push(timing); assert.ok(timing.passed, JSON.stringify(timing))
  }
  // A committed administrator write remains successful when queue reads fail.
  await reviewer.getByRole('button', { name: 'Edit fields ↗', exact: true }).click()
  await reviewer.getByLabel('Title', { exact: true }).fill('Confirmed write with unavailable queue')
  await reviewer.route(api + '/api/admin/events', route => route.abort())
  let confirmedEdits = 0
  reviewer.on('request', request => {
    if (request.url().endsWith(`/api/admin/events/${event.event_id}/review`) && request.method() === 'POST' && request.postDataJSON()?.action === 'edit') confirmedEdits++
  })
  const savedEdit = reviewer.waitForResponse(response => response.url().endsWith(`/events/${event.event_id}/review`) && response.request().postDataJSON()?.action === 'edit')
  await reviewer.getByRole('button', { name: 'Save draft', exact: true }).click()
  assert.equal((await savedEdit).status(), 200)
  await reviewer.getByText('Review saved. The queue could not refresh; refresh it manually.', { exact: true }).waitFor()
  assert.equal((await call('/api/events', undefined, true))[0].title, 'Confirmed write with unavailable queue')
  assert.equal(confirmedEdits, 1)
  assert.equal(await reviewer.getByRole('button', { name: 'Save draft', exact: true }).count(), 0)
  assert.ok(!(await reviewer.locator('body').innerText()).includes('The review could not be confirmed.'))
  await reviewer.unroute(api + '/api/admin/events')
  await reviewer.getByRole('button', { name: 'Refresh events ↻', exact: true }).click()
  const withdrawalStarted = performance.now()
  const withdrawalRevision = Number(await page.locator('[data-route-refresh-revision]').getAttribute('data-route-refresh-revision'))
  await call(`/api/events/${event.event_id}/review`, { action: 'expire', actor: 'P4-test' }, true)
  await page.locator('[data-event-revisions=""]').waitFor()
  await until(async () => Number(await page.locator('[data-route-refresh-revision]').getAttribute('data-route-refresh-revision')) > withdrawalRevision)
  assert.ok(performance.now() - withdrawalStarted <= 5000)
  await reviewContext.close()
  console.log('LOCAL render timings ms: ' + JSON.stringify(timings.map(value => ({ map: value.map_ms, routes: value.routes_ms }))))
  pass('three admin approvals rendered within 5 seconds, pending edit isolation, confirmed write with failed refresh and polling withdrawal')
  // The fixed seed demonstration retains its explicit identity.
  const seed = await context.newPage(), seedChats = []
  seed.on('pageerror', error => errors.push(error.message))
  seed.on('request', request => { if (request.url().endsWith('/api/ai/chat')) seedChats.push(request.url()) })
  await seed.goto(web + '?data=seed'); await navigate(seed, 'Agent'); await seed.getByText('Seed conversation · template replies · no live AI.', { exact: false }).waitFor()
  await seed.getByRole('button', { name: /^Tai Wai to Admiralty, less walking/ }).click(); await seed.getByRole('button', { name: 'Inspect these seed routes →', exact: true }).click(); await seed.getByRole('heading', { name: 'Tai Wai → Admiralty' }).waitFor()
  assert.deepEqual(seedChats, []); assert.deepEqual(errors, [])
  assert.deepEqual(forbiddenHeaders, [])
  assert.equal(await page.evaluate(() => Object.keys(localStorage).length + Object.keys(sessionStorage).length), 0)
  pass('seed isolation, no browser errors, no stored reviewer credentials')
  console.log(JSON.stringify({ passed: true, checks: checks.length, mediaCreated: false }))
})().catch(async error => {
  console.error(error.stack)
  if (publicPage) console.error('Visible DOM: ' + (await publicPage.locator('body').innerText().catch(() => '')).slice(-9000))
  for (const child of children) if (child.exitCode !== null) console.error(child.logs())
  process.exitCode = 1
}).finally(async () => {
  await browser?.close()
  for (const child of children) if (child.exitCode === null) {
    if (process.platform === 'win32') await new Promise(resolve => spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }).on('exit', resolve))
    else child.kill('SIGTERM')
  }
})
