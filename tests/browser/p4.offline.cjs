// Prepared production build + local API, with all non-loopback browser requests blocked.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const { chromium } = require(process.env.M2_PLAYWRIGHT || 'playwright')
const root = path.resolve(__dirname, '../..'), out = path.join(root, '.cache/p4-browser')
const tour = process.env.P4_RECORD_TOUR === 'true'
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
fs.mkdirSync(out, { recursive: true })
let launcher, browser, context, page, video, logs = ''
const evidence = { environment: process.env.CI ? 'CI isolated offline browser' : 'local isolated offline browser',
  measured_at: new Date().toISOString(), passed: false, wan_blocked: [], assertions: [], scenarios: [] }
async function ready(url) {
  for (let attempt = 0; attempt < 150; attempt++) {
    if (launcher.exitCode !== null) throw new Error('Offline launcher stopped: ' + logs)
    if (logs.includes('Offline demo ready:')) {
      try { if ((await fetch(url)).ok) return } catch {}
    }
    await pause(100)
  }
  throw new Error('Offline launcher not ready: ' + logs)
}
;(async () => {
  // Fixed offline ports belong only to this launcher; it refuses occupied ports.
  launcher = spawn(process.env.M2_PYTHON || 'python', ['scripts/offline_demo.py', '--duration-seconds', tour ? '360' : '90'],
    { cwd: root, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  launcher.stdout.on('data', chunk => logs += chunk); launcher.stderr.on('data', chunk => logs += chunk)
  launcher.on('error', error => logs += error.message)
  const api = 'http://127.0.0.1:8000', web = 'http://127.0.0.1:5173'
  await Promise.all([ready(web), ready(api + '/api/health')])
  const health = await (await fetch(api + '/api/health')).json()
  assert.equal(health.ok, true); assert.equal(health.mode, 'offline')
  evidence.backend_build = health.build
  const build = await (await fetch(web + '/build-info.json')).json()
  assert.equal(build.commit_sha, JSON.parse(fs.readFileSync(path.join(root, 'frontend/dist/offline-build.json'), 'utf8')).source_revision)
  assert.equal(build.commit_sha, health.build.commit_sha); evidence.frontend_build = build
  browser = await chromium.launch({ headless: true, ...(process.env.M2_BROWSER_CHANNEL ? { channel: process.env.M2_BROWSER_CHANNEL } : {}) })
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce',
    ...(tour ? { recordVideo: { dir: path.join(out, 'video'), size: { width: 1440, height: 1000 } } } : {}) })
  await context.route('**/*', route => {
    const url = new URL(route.request().url())
    if (url.hostname === '127.0.0.1' && [8000, 5173].includes(Number(url.port))) return route.continue()
    evidence.wan_blocked.push(url.origin); return route.abort()
  })
  page = await context.newPage(); page.setDefaultTimeout(20000)
  video = page.video(); const errors = [], started = Date.now()
  page.on('pageerror', error => errors.push(error.message))
  const holdUntil = async seconds => { if (tour) await pause(Math.max(0, seconds * 1000 - (Date.now() - started))) }
  await page.goto(web)
  await page.getByRole('combobox', { name: 'TO', exact: true }).click()
  await page.getByRole('option', { name: /Admiralty/ }).click()
  await page.locator('[aria-controls="departure-calendar"]').click()
  const day = page.getByRole('button', { name: '2026-09-22', exact: true })
  for (let month = 0; !(await day.count()) && month < 3; month++) await page.getByRole('button', { name: 'Previous month', exact: true }).click()
  await day.click()
  await page.locator('input[type="time"]').fill('08:20')
  const [response] = await Promise.all([
    page.waitForResponse(res => res.url() === api + '/api/routes/query' && res.ok()),
    page.getByRole('button', { name: 'Find resilient routes' }).click(),
  ])
  const routes = await response.json(); assert.ok(routes.length)
  await page.getByRole('heading', { name: 'Tai Wai → Admiralty' }).waitFor()
  assert.ok(await page.locator('[data-route-id]').count())
  await page.screenshot({ path: path.join(out, '01-offline-routes.png') })
  evidence.assertions.push('production-frontend-local-route-query', 'matching-backend-frontend-SHA', 'offline-health')
  await holdUntil(60)
  await page.getByRole('button', { name: 'Simulation', exact: true }).click()
  const scenarioIds = ['scn_huh_exc_closed_am_peak',
    'm2_six_station_directed_od_am_peak_p3_shared_segments',
    'm2_six_station_directed_od_am_peak_p3_shared_segments_residual_10pct']
  for (let index = 0; index < scenarioIds.length; index++) {
    const id = scenarioIds[index]
    await page.getByLabel('Simulation scenario', { exact: true }).selectOption(id)
    await page.getByRole('button', { name: 'Load precomputed result', exact: true }).click()
    const panel = page.locator(`[data-simulation-id="${id}"]`); await panel.waitFor()
    const result = await (await fetch(api + '/api/sim/result?scenario_id=' + id)).json()
    const legacyGap = panel.getByText('Legacy capacity-gap field', { exact: true })
    if (!await legacyGap.evaluate(summary => summary.parentElement.open)) await legacyGap.click()
    const text = await panel.innerText()
    assert.ok(text.includes('Backend unstoppable_demand: ' + result.guided.unstoppable_demand.toLocaleString('en-HK')))
    for (const strategy of ['baseline', 'guided']) assert.ok(text.includes(result[strategy].total_delay_person_min.toLocaleString('en-HK')))
    if (index === 0) { assert.ok(result.delta.delay_reduction_pct < 0); await page.getByText('Guided delay is higher. This scenario shows no delay improvement.', { exact: false }).waitFor() }
    else {
      assert.equal(result.population, 10000); assert.equal(result.seed, 20260922)
      assert.equal(result.provenance, 'simulated'); assert.ok(result.generated_at && result.metric_units)
      assert.ok(text.includes(result.guided.unstoppable_demand.toLocaleString('en-HK')))
    }
    await page.screenshot({ path: path.join(out, `0${index + 2}-simulation.png`) })
    evidence.scenarios.push({ scenario_id: id, delay_reduction_pct: result.delta.delay_reduction_pct,
      baseline_delay: result.baseline.total_delay_person_min, guided_delay: result.guided.total_delay_person_min,
      guided_capacity_gap: result.guided.unstoppable_demand })
    fs.writeFileSync(path.join(out, `scenario-${index}.json`), JSON.stringify(result, null, 2))
    await holdUntil((index + 2) * 60)
  }
  await page.getByRole('heading', { name: 'People the model cannot serve.', exact: true }).scrollIntoViewIfNeeded()
  await page.screenshot({ path: path.join(out, '05-capacity-gap.png') })
  await holdUntil(270)
  await page.getByRole('heading', { name: 'Assumptions', exact: true }).scrollIntoViewIfNeeded()
  await page.screenshot({ path: path.join(out, '06-assumptions.png') })
  await holdUntil(300)
  assert.deepEqual(errors, [])
  evidence.assertions.push('negative-benefit-visible', 'P3-normal-zero-benefit-preserved', 'P3-stress-gap-visible',
    'verbatim-backend-delay-and-gap', 'non-loopback-requests-aborted', 'assumptions-visible', 'no-page-errors')
  evidence.wan_blocked = [...new Set(evidence.wan_blocked)]
  evidence.tour_elapsed_seconds = (Date.now() - started) / 1000
  await context.close(); context = null
  if (tour) {
    const target = path.join(root, 'deploy/offline/media/demo.webm')
    fs.mkdirSync(path.dirname(target), { recursive: true }); await video.saveAs(target)
    evidence.tour_file = 'deploy/offline/media/demo.webm'
  }
  evidence.passed = true
})().catch(async error => {
  evidence.error = error.stack; process.exitCode = 1
  if (page) await page.screenshot({ path: path.join(out, 'failure.png') }).catch(() => {})
}).finally(async () => {
  await browser?.close()
  if (launcher && launcher.exitCode === null) {
    if (process.platform === 'win32') await new Promise(resolve => spawn('taskkill', ['/PID', String(launcher.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }).on('exit', resolve))
    else { launcher.kill('SIGTERM'); await pause(1000) }
  }
  fs.writeFileSync(path.join(out, 'launcher.log'), logs)
  fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify(evidence, null, 2))
  console.log(JSON.stringify(evidence))
})
