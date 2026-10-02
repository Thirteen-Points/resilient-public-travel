// Default: read-only production probe. P3_ACCEPTANCE=1 explicitly runs review.
// Use an existing debug-enabled admin browser via P3_CDP_URL, or credentials
// supplied by B/C in process environment. Never save session state or headers.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict')
const { chromium } = require(process.env.M2_PLAYWRIGHT || 'playwright')
const { publication, until, frames, futureJourney, mapPainted } = require('./p3-render-timing.cjs')
const root = path.resolve(__dirname, '../..'), out = path.join(root, '.cache/p3-browser/online')
fs.mkdirSync(out, { recursive: true })
const api = process.env.P3_API_URL || 'https://resilient-public-travel-api.onrender.com'
const web = process.env.P3_WEB_URL || 'https://resilient-public-travel.pages.dev/'
const evidence = { at: new Date().toISOString(), web, api, environment: 'production Pages + Render', mode: process.env.P3_ACCEPTANCE === '1' ? 'publication acceptance' : 'read-only probe', probes: [], rounds: [], blockers: [], passed: false }
const runId = evidence.at.replace(/[:.]/g, '-')
let browser, remote, admin, visitorContext, cleanup
async function probe(endpoint, body) {
  const started = performance.now()
  try {
    const response = await fetch(api + endpoint, { method: body === undefined ? 'GET' : 'POST', headers: body === undefined ? {} : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(60000) })
    const value = await response.json()
    evidence.probes.push({ path: endpoint, status: response.status, elapsed_ms: Math.round(performance.now() - started), body: value })
    return value
  } catch (error) { evidence.probes.push({ path: endpoint, error: error.message, elapsed_ms: Math.round(performance.now() - started) }); return null }
}
;(async () => {
  // Initial health is deliberately first; do not claim it proves a cold start.
  await probe('/api/health')
  await probe('/api/meta')
  await probe('/api/sim/result?scenario_id=scn_huh_exc_closed_am_peak')
  await probe('/api/sim/result?scenario_id=m2_six_station_directed_od_am_peak')
  await probe('/api/ai/chat', { message: 'Explain the current route and its limitations.', origin: 'TAW', destination: 'ADM', depart_at: new Date().toISOString() })
  browser = await chromium.launch({ headless: true, ...(process.env.M2_BROWSER_CHANNEL ? { channel: process.env.M2_BROWSER_CHANNEL } : {}) })
  visitorContext = await browser.newContext({ viewport: { width: 1440, height: 1000 }, recordVideo: { dir: path.join(out, 'video') }, reducedMotion: 'reduce' })
  const visitor = await visitorContext.newPage(), visitorErrors = [], forbiddenHeaders = []
  visitor.on('pageerror', error => visitorErrors.push(error.message))
  visitor.on('request', request => {
    if (request.url().startsWith(api) && (request.headers()['x-review-token'] || request.headers()['x-csrf-token'] || request.headers().authorization)) forbiddenHeaders.push(new URL(request.url()).pathname)
  })
  await visitor.goto(web, { timeout: 60000 })
  await visitor.getByRole('button', { name: 'Find resilient routes' }).waitFor({ timeout: 60000 })
  await visitor.getByRole('combobox', { name: 'TO', exact: true }).click(); await visitor.getByRole('option', { name: /Admiralty/ }).click()
  evidence.departure_hkt = await futureJourney(visitor)
  await visitor.getByRole('button', { name: 'Find resilient routes' }).click(); await visitor.getByRole('heading', { name: 'Tai Wai → Admiralty' }).waitFor()
  await frames(visitor); await visitor.screenshot({ path: path.join(out, 'public-routes.png'), fullPage: true })
  evidence.public_query = { rendered: true, errors: visitorErrors, reviewer_headers: forbiddenHeaders, browser_storage_keys: await visitor.evaluate(() => Object.keys(localStorage).length + Object.keys(sessionStorage).length) }
  if (process.env.P3_ACCEPTANCE !== '1') {
    evidence.blockers.push('Read-only run: no publication/withdrawal attempted. Three production timing rounds remain unverified.')
    if (!await visitor.locator('[data-route-refresh-revision]').count()) evidence.blockers.push('Production frontend has not deployed P3 render timing markers.')
    return
  }
  assert.ok(await visitor.locator('[data-route-refresh-revision]').count(), 'Deploy this FreddyP3 frontend before production acceptance')
  assert.ok(process.env.P3_EVENT_ID, 'B/C must supply a prepared, simulated P3 acceptance event via P3_EVENT_ID')
  if (process.env.P3_CDP_URL) {
    remote = await chromium.connectOverCDP(process.env.P3_CDP_URL)
    const candidates = remote.contexts().flatMap(context => context.pages()).filter(page => page.url().startsWith(api + '/admin'))
    assert.equal(candidates.length, 1, 'Exactly one existing application administrator tab is required')
    admin = candidates[0]
  } else {
    assert.ok(process.env.P3_ADMIN_USER && process.env.P3_ADMIN_PASSWORD, 'Existing browser connection unavailable; B/C can supply credentials locally without posting them in chat')
    const context = await browser.newContext()
    const login = await context.request.post(api + '/api/admin/login', { data: { username: process.env.P3_ADMIN_USER, password: process.env.P3_ADMIN_PASSWORD } })
    assert.ok(login.ok(), `Admin login HTTP ${login.status()}`)
    admin = await context.newPage(); await admin.goto(api + '/admin/')
  }
  const sessionResponse = await admin.context().request.get(api + '/api/admin/session')
  assert.ok(sessionResponse.ok(), 'The Render dashboard session is distinct from the application review session; log in to /admin/')
  const session = await sessionResponse.json()
  async function call(endpoint, body) {
    const response = body === undefined ? await admin.context().request.get(api + '/api/admin' + endpoint) : await admin.context().request.post(api + '/api/admin' + endpoint, { data: body, headers: { 'X-CSRF-Token': session.csrf_token } })
    assert.ok(response.ok(), `${endpoint}: HTTP ${response.status()}`); return response.json()
  }
  const id = process.env.P3_EVENT_ID
  let event = (await call('/events')).find(value => value.event_id === id)
  assert.ok(event && event.provenance === 'simulated' && event.title.includes('P3') && event.confidence >= .55, 'Use an explicitly simulated, corroborated P3 test event; never select a real incident')
  assert.equal(event.status, 'pending_review', 'Prepare an unapproved event first; retain any existing production events')
  assert.ok(event.window.end && Date.parse(event.window.end) > Date.now() && Date.parse(event.window.start) < Date.now(), 'B/C must supply a currently effective, bounded test window')
  assert.ok(Date.parse(event.window.end) > Date.parse(evidence.departure_hkt), 'The test window must contain the future journey')
  assert.ok(Date.parse(event.window.end) - Date.now() <= 60 * 60000, 'Test event must expire within one hour')
  cleanup = async () => {
    const current = (await call('/events')).find(value => value.event_id === id)
    if (current && ['published', 'updated'].includes(current.status)) {
      await call(`/events/${id}/review`, { action: 'expire', expected_version: current.version, reason: 'P3 acceptance cleanup after interruption/failure.' })
      evidence.cleanup = 'Selected simulated P3 event withdrawn after interrupted acceptance.'
    }
  }
  const baseline = (await (await fetch(api + '/api/events/published')).json()).map(value => `${value.event_id}@${value.version}`)
  assert.ok(!baseline.some(value => value.startsWith(id + '@')), 'Pending event already exposed')
  for (let round = 1; round <= 3; round++) {
    if (round > 1) {
      const previous = (await (await fetch(api + '/api/events/published')).json()).find(value => value.event_id === id)
      event = await call(`/events/${id}/review`, { action: 'edit', expected_version: event.version, edits: { title: `【模拟 P3 发布验收】round ${round}` }, reason: 'Explicit P3 acceptance test; no real disruption asserted.' })
      const stillApproved = (await (await fetch(api + '/api/events/published')).json()).find(value => value.event_id === id)
      assert.equal(stillApproved.version, previous.version); assert.equal(stillApproved.title, previous.title)
      evidence.pending_edits_excluded = true
    }
    await admin.getByRole('button', { name: 'Reports & Review', exact: true }).click()
    await admin.getByRole('button', { name: 'Refresh events ↻' }).click()
    await admin.getByLabel('Search queue').fill(id)
    await admin.getByRole('button').filter({ hasText: event.title }).first().click()
    await admin.getByRole('button', { name: 'Publish →', exact: true }).click()
    evidence.rounds.push({ round, ...await publication(visitor, admin, id) })
    fs.appendFileSync(path.join(out, 'publication-history.jsonl'), JSON.stringify({ run: evidence.at, ...evidence.rounds.at(-1) }) + '\n')
    fs.writeFileSync(path.join(out, 'acceptance.json'), JSON.stringify(evidence, null, 2))
    await visitor.screenshot({ path: path.join(out, `published-${round}.png`), fullPage: true })
    event = (await call('/events')).find(value => value.event_id === id)
  }
  await admin.getByRole('button', { name: 'Withdraw event', exact: true }).click()
  const previousRevision = Number(await visitor.locator('[data-route-refresh-revision]').getAttribute('data-route-refresh-revision'))
  const started = performance.now()
  await admin.getByRole('button', { name: 'Confirm withdrawal', exact: true }).click()
  await until(async () => !(await visitor.locator('[data-event-revisions]').getAttribute('data-event-revisions')).includes(id + '@'))
  await until(async () => Number(await visitor.locator('[data-route-refresh-revision]').getAttribute('data-route-refresh-revision')) > previousRevision)
  await frames(visitor); evidence.withdrawal_ms = Math.round(performance.now() - started)
  await visitor.screenshot({ path: path.join(out, 'withdrawn.png'), fullPage: true })
  await visitorContext.setOffline(true)
  await visitor.getByText('displayed', { exact: false }).filter({ hasText: 'stale' }).first().waitFor()
  assert.ok(await visitor.locator('[data-route-id]').count()); assert.ok(await mapPainted(visitor))
  await visitor.screenshot({ path: path.join(out, 'offline-retained.png'), fullPage: true })
  await visitorContext.setOffline(false)
  await visitor.getByRole('button', { name: 'Refresh', exact: true }).click()
  await until(async () => !(await visitor.locator('body').innerText()).includes('may be stale'))
  await visitor.screenshot({ path: path.join(out, 'recovered.png'), fullPage: true })
  evidence.offline_recovery = true
  assert.deepEqual(forbiddenHeaders, []); assert.deepEqual(visitorErrors, [])
  evidence.passed = evidence.rounds.length === 3 && evidence.rounds.every(value => value.passed) && evidence.withdrawal_ms <= 5000
  if (!evidence.passed) process.exitCode = 1
})().catch(error => { evidence.blockers.push(error.message); process.exitCode = 1 }).finally(async () => {
  if (cleanup) await cleanup().catch(error => evidence.blockers.push(`P3 test-event cleanup failed: ${error.message}`))
  // Disconnect the client without closing a user's existing remote browser.
  await visitorContext?.close(); await browser?.close()
  fs.writeFileSync(path.join(out, `acceptance-${runId}.json`), JSON.stringify(evidence, null, 2))
  fs.writeFileSync(path.join(out, 'acceptance.json'), JSON.stringify(evidence, null, 2)); console.log(JSON.stringify({ at: evidence.at, mode: evidence.mode, probes: evidence.probes.map(({ path, status, elapsed_ms, error }) => ({ path, status, elapsed_ms, error })), public_query: evidence.public_query, rounds: evidence.rounds, blockers: evidence.blockers, passed: evidence.passed }))
  if (remote) process.exit(process.exitCode || 0)
})
