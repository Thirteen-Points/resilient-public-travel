// Real backend integration and explicitly injected failure cases. No media is
// recorded and no delivery/report artifacts are created by this regression.
const path = require('node:path'), net = require('node:net')
const { spawn } = require('node:child_process')
const assert = require('node:assert/strict')
const { chromium } = require(process.env.M2_PLAYWRIGHT || 'playwright')
const { publication, until, frames } = require('./p3-render-timing.cjs')
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
  await page.getByRole('option', { name: new RegExp(`^${name} MTR ·`) }).click()
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
  const page = await context.newPage(); publicPage = page; page.setDefaultTimeout(15000)
  page.on('pageerror', error => errors.push(error.message))
  const routeBodies = [], chatBodies = [], preferenceBodies = []
  page.on('request', request => {
    if (request.url() === api + '/api/routes/query') routeBodies.push(request.postDataJSON())
    if (request.url() === api + '/api/ai/chat') chatBodies.push(request.postDataJSON())
    if (request.url() === api + '/api/persona/parse') preferenceBodies.push(request.postDataJSON())
  })
  await page.goto(web); await page.getByRole('button', { name: 'Find resilient routes' }).waitFor()
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
  pass('real preferences: preview, confirmation, accessible routing')
  await page.getByRole('button', { name: 'Agent', exact: true }).click()
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
  await page.getByRole('button', { name: 'Plan journey', exact: true }).click()
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
  await page.getByRole('button', { name: 'How it works', exact: true }).click(); releaseRoutes(); await page.unroute(api + '/api/routes/query'); await frames(page)
  assert.ok(await page.getByRole('heading', { name: 'Source freshness & collection', exact: true }).isVisible())
  assert.equal(await page.locator('#routes-heading').count(), 0)
  await page.getByRole('button', { name: 'Plan journey', exact: true }).click()
  await page.getByRole('button', { name: 'Find resilient routes' }).click(); await page.getByRole('heading', { name: 'Tai Wai → Hung Hom' }).waitFor()
  pass('changing stations or leaving the planner cancels obsolete route navigation')
  // Live comparison stays truthful on old servers; future snapshot headers are
  // tested separately using an explicitly injected metadata contract.
  const compareStart = routeBodies.length
  await page.getByRole('button', { name: 'Compare', exact: true }).click()
  await page.locator('[data-comparison-verified]').waitFor()
  const pair = routeBodies.slice(compareStart).filter(body => body.event_ids)
  assert.equal(pair.length, 2); assert.equal(pair[0].origin, pair[1].origin); assert.equal(pair[0].destination, pair[1].destination); assert.equal(pair[0].depart_at, pair[1].depart_at)
  assert.deepEqual(pair[0].event_ids, pair[1].event_ids); assert.equal(pair[1].profile.mobility, 'wheelchair')
  const actualVerified = await page.locator('[data-comparison-verified]').getAttribute('data-comparison-verified')
  if (actualVerified === 'false') await page.getByText('Pair consistency: unverified.', { exact: false }).waitFor()
  await page.route(api + '/api/routes/query', async route => { const response = await route.fetch(); await route.fulfill({ response, headers: { ...response.headers(), 'X-Route-Snapshot': 'injected-p4-matching', 'Access-Control-Expose-Headers': 'X-Route-Snapshot' } }) })
  await page.getByRole('button', { name: 'Refresh both profiles', exact: true }).click(); await page.locator('[data-comparison-verified="true"]').waitFor()
  await page.getByText('calculation snapshot injected-p4-matching', { exact: false }).waitFor()
  await page.unroute(api + '/api/routes/query')
  let snapshotCalls = 0
  await page.route(api + '/api/routes/query', async route => { const response = await route.fetch(); await route.fulfill({ response, headers: { ...response.headers(), 'X-Route-Snapshot': `injected-p4-mismatch-${++snapshotCalls}`, 'Access-Control-Expose-Headers': 'X-Route-Snapshot' } }) })
  await page.getByRole('button', { name: 'Refresh both profiles', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: 'Both profiles were retried' }).waitFor()
  assert.equal(snapshotCalls, 4); await page.getByText('Previous comparison retained', { exact: false }).waitFor()
  await page.unroute(api + '/api/routes/query'); pass('comparison: actual pair plus injected matching/mismatched snapshot headers')
  // Actual precomputed scenarios: unchanged results, modest improvement and gap.
  await page.getByRole('button', { name: 'Simulation', exact: true }).click(); await page.getByRole('button', { name: 'Load precomputed result', exact: true }).click()
  await page.locator(`[data-simulation-id="${normalId}"]`).waitFor()
  const normal = await call(`/api/sim/result?scenario_id=${normalId}`)
  await page.getByText('Delay is unchanged.', { exact: false }).waitFor()
  for (const strategy of ['baseline', 'guided']) assert.ok((await page.locator(`[data-strategy="${strategy}"]`).innerText()).includes(normal[strategy].total_delay_person_min.toLocaleString('en-HK')))
  await page.getByLabel('Simulation scenario', { exact: true }).selectOption(stressId); await page.getByRole('button', { name: 'Load precomputed result', exact: true }).click()
  await page.locator(`[data-simulation-id="${stressId}"]`).waitFor()
  const stress = await call(`/api/sim/result?scenario_id=${stressId}`)
  await page.getByText('Sensitivity experiment:', { exact: false }).waitFor(); await page.getByText('Backend delay change: 1.6% reduction.', { exact: false }).waitFor()
  const simText = await page.locator('[data-simulation-id]').innerText()
  assert.ok(simText.includes('199')); assert.equal(stress.guided.unassigned_demand, 199)
  assert.ok(simText.includes('1.99%')); assert.ok(simText.includes('15-minute limit covers extra route travel'))
  assert.ok(simText.includes('Not supplied — age unknown'))
  await page.getByText('Inspect route and shared-segment loads', { exact: true }).click()
  const resourceRows = page.getByRole('region', { name: 'guided shared segment table', exact: true }).locator('tbody tr')
  assert.equal(await resourceRows.count(), stress.guided.resource_load.length)
  await page.getByText('Use another scenario id', { exact: true }).click()
  await page.getByLabel('Simulation scenario id', { exact: true }).fill('injected-missing-p4-scenario'); await page.getByRole('button', { name: 'Load precomputed result', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: 'SIM_RESULT_NOT_FOUND' }).waitFor()
  assert.equal(await page.locator('[data-simulation-id]').getAttribute('data-simulation-id'), stressId)
  pass('real simulations: unchanged delay, 1.6% stress reduction, 199 unassigned, retained missing scenario')
  let releaseSimulation
  await page.route(api + '/api/sim/result?scenario_id=' + normalId, async route => { await new Promise(resolve => releaseSimulation = resolve); await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(normal) }).catch(() => {}) })
  await page.getByLabel('Simulation scenario', { exact: true }).selectOption(normalId); await page.getByRole('button', { name: 'Load precomputed result', exact: true }).click(); await until(() => Boolean(releaseSimulation))
  await page.getByLabel('Simulation scenario', { exact: true }).selectOption(stressId); await page.getByRole('button', { name: 'Load precomputed result', exact: true }).click()
  await page.getByRole('button', { name: 'Load precomputed result', exact: true }).waitFor(); releaseSimulation(); await page.unroute(api + '/api/sim/result?scenario_id=' + normalId); await frames(page)
  assert.equal(await page.locator('[data-simulation-id]').getAttribute('data-simulation-id'), stressId)
  pass('changing simulation scenarios rejects an obsolete completion')
  // Source failure is isolated from route queries and preserves previous status.
  await page.getByRole('button', { name: 'How it works', exact: true }).click(); await page.locator('[data-source="mtr"]').waitFor()
  const actualSources = await call('/api/sources/status'); assert.equal(actualSources.publishes_events, false)
  if (!actualSources.sources.mtr.last_success_at) await page.getByText('No persistent last-success time supplied.', { exact: false }).first().waitFor()
  await page.route(api + '/api/sources/status', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Injected collection failure' }) }))
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: 'Collection status refresh failed' }).waitFor()
  assert.ok(await page.locator('[data-source="mtr"]').isVisible())
  await page.getByRole('button', { name: 'Plan journey', exact: true }).click(); await page.getByRole('button', { name: 'Find resilient routes' }).click(); await page.getByRole('heading', { name: 'Tai Wai → Hung Hom' }).waitFor()
  await page.unroute(api + '/api/sources/status'); pass('actual source status and isolated collection failure')
  // Retain previous simulation while offline, then recover the actual selection.
  await page.getByRole('button', { name: 'Simulation', exact: true }).click(); await page.getByLabel('Simulation scenario', { exact: true }).selectOption(stressId)
  await context.setOffline(true); await page.getByRole('alert').filter({ hasText: 'Offline. Previous simulation retained' }).waitFor()
  assert.equal(await page.locator('[data-simulation-id]').getAttribute('data-simulation-id'), stressId)
  await context.setOffline(false); await page.getByRole('alert').filter({ hasText: 'Offline. Previous simulation retained' }).waitFor({ state: 'hidden' })
  pass('offline result retention and automatic online recovery')
  // Keyboard focus, large text, contrast, mobile, and scrollable tables.
  for (const width of [1440, 800, 390, 320]) {
    await page.setViewportSize({ width, height: 900 }); await noOverflow(page, `simulation ${width}`)
    await page.getByRole('button', { name: 'Large text', exact: true }).click(); await page.getByRole('button', { name: 'High contrast', exact: true }).click(); await noOverflow(page, `simulation large text ${width}`)
    await page.getByRole('button', { name: 'Large text', exact: true }).click(); await page.getByRole('button', { name: 'High contrast', exact: true }).click()
    await page.getByRole('button', { name: 'Compare', exact: true }).click(); await page.getByRole('button', { name: 'Refresh both profiles', exact: true }).waitFor(); await noOverflow(page, `comparison ${width}`)
    await page.getByRole('button', { name: 'How it works', exact: true }).click(); await noOverflow(page, `sources ${width}`)
    await page.getByRole('button', { name: 'Agent', exact: true }).click(); await noOverflow(page, `agent ${width}`)
    const prompt = page.getByLabel('ASK ABOUT THE CURRENT JOURNEY'); await prompt.fill('Keyboard focus check'); await prompt.press('Tab')
    assert.ok(await page.getByRole('button', { name: 'Send message', exact: true }).evaluate(button => button === document.activeElement && getComputedStyle(button).outlineStyle !== 'none'))
    await page.getByRole('button', { name: 'Plan journey', exact: true }).click(); await noOverflow(page, `planner ${width}`)
    await page.getByRole('button', { name: 'Simulation', exact: true }).click()
  }
  pass('320–1440 px layouts, enlarged text, high contrast and keyboard focus')
  // Three real approvals, each measured after map and route-card rendering.
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.getByRole('button', { name: 'Plan journey', exact: true }).click()
  await page.getByRole('button', { name: 'Commuter', exact: true }).click(); await selectStation(page, 'TO', 'Admiralty'); await page.getByRole('button', { name: 'Find resilient routes' }).click(); await page.getByRole('heading', { name: 'Tai Wai → Admiralty' }).waitFor()
  const reviewContext = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
  await reviewContext.route('**/*', route => route.request().url().startsWith(web) || route.request().url().startsWith(api) ? route.continue() : route.abort())
  const reviewer = await reviewContext.newPage(); reviewer.on('pageerror', error => errors.push(error.message))
  await reviewer.goto(web); await reviewer.getByRole('button', { name: 'Report', exact: true }).click(); await reviewer.getByLabel('What did you see?').fill('【模拟 P4 浏览器测试】东铁线红磡至会展信号故障，暂停服务。')
  await reviewer.getByRole('button', { name: /Send unverified report/ }).click(); await reviewer.getByText('Report received — not yet verified.').waitFor()
  await reviewer.getByRole('button', { name: 'Review', exact: true }).click(); await reviewer.getByLabel('Temporary credential').fill('m2-isolated-test'); await reviewer.getByRole('button', { name: 'Connect reviewer', exact: true }).click()
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
      await call(`/api/events/${event.event_id}/review`, { action: 'edit', actor: 'P4-test', edits: { title: `【模拟 P4 浏览器测试】revision ${round + 1}` } }, true)
      assert.equal((await call('/api/events/published'))[0].title, approvedTitle)
    } else assert.deepEqual(await call('/api/events/published'), [])
    await reviewer.getByRole('button', { name: 'Refresh events ↻', exact: true }).click(); await reviewer.getByRole('button', { name: 'Publish →', exact: true }).click()
    const timing = await publication(page, reviewer, event.event_id); timings.push(timing); assert.ok(timing.passed, JSON.stringify(timing))
  }
  await call(`/api/events/${event.event_id}/review`, { action: 'expire', actor: 'P4-test' }, true)
  await page.locator('[data-event-revisions=""]').waitFor(); await reviewContext.close()
  console.log('LOCAL render timings ms: ' + JSON.stringify(timings.map(value => ({ map: value.map_ms, routes: value.routes_ms }))))
  pass('three real approvals: rendered map and route cards within 5 seconds; pending revision isolation; withdrawal')
  // The fixed seed demonstration retains its explicit identity.
  const seed = await context.newPage(), seedChats = []
  seed.on('request', request => { if (request.url().endsWith('/api/ai/chat')) seedChats.push(request.url()) })
  await seed.goto(web + '?data=seed'); await seed.getByRole('button', { name: 'Agent', exact: true }).click(); await seed.getByText('Seed conversation · template replies · no live AI.', { exact: false }).waitFor()
  await seed.getByRole('button', { name: /^Tai Wai to Admiralty, less walking/ }).click(); await seed.getByRole('button', { name: 'Inspect these seed routes →', exact: true }).click(); await seed.getByRole('heading', { name: 'Tai Wai → Admiralty' }).waitFor()
  assert.deepEqual(seedChats, []); assert.deepEqual(errors, [])
  assert.equal(await page.evaluate(() => Object.keys(localStorage).length + Object.keys(sessionStorage).length), 0)
  pass('seed isolation, no browser errors, no stored reviewer credentials')
  console.log(JSON.stringify({ passed: true, checks: checks.length, actualComparisonVerified: actualVerified === 'true', mediaCreated: false }))
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
