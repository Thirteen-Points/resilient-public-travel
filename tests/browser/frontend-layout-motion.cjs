// Targeted passenger layout and navigation acceptance against the isolated API.
// Run with LAYOUT_BASELINE=1 before editing to capture the original three pages.
const path = require('node:path'), fs = require('node:fs'), net = require('node:net')
const { spawn } = require('node:child_process')
const assert = require('node:assert/strict')
const { chromium } = require(process.env.M2_PLAYWRIGHT || 'playwright')
const { navigate, assertRemovedPages } = require('./public-ui.cjs')
const root = path.resolve(__dirname, '../..'), children = [], browserErrors = [], checks = []
const baseline = process.env.LAYOUT_BASELINE === '1'
const folder = path.join(root, '.cache/frontend-layout-motion', baseline ? 'before' : process.env.LAYOUT_FORCE_FALLBACK === '1' ? 'fallback' : 'after')
fs.mkdirSync(folder, { recursive: true })
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
async function frames(page, count = 2) {
  await page.evaluate(count => new Promise(resolve => { const step = () => --count ? requestAnimationFrame(step) : resolve(); requestAnimationFrame(step) }), count)
}
async function settled(page) {
  await page.waitForFunction(() => !document.getAnimations().some(animation => animation.playState === 'running' && animation.effect?.pseudoElement?.startsWith('::view-transition')))
  await pause(300); await frames(page)
}
async function mapPaths(page) {
  return page.locator('#journey-map .leaflet-overlay-pane svg path').evaluateAll(paths => paths.map(path => {
    const s = getComputedStyle(path)
    return { d: path.getAttribute('d') ?? '', stroke: s.stroke, fill: s.fill, strokeOpacity: Number(s.strokeOpacity), dash: s.strokeDasharray }
  }).filter(path => path.strokeOpacity > 0))
}
function contrast(first, second) {
  const luminance = color => color.match(/[\d.]+/g).slice(0, 3).map(Number).map(value => value / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4).reduce((sum, value, i) => sum + value * [.2126, .7152, .0722][i], 0)
  const a = luminance(first), b = luminance(second)
  return (Math.max(a, b) + .05) / (Math.min(a, b) + .05)
}
async function noOverflow(page, name, width) {
  const layout = await rects(page)
  assert.ok(layout.document <= layout.viewport + 1, `${width} ${name}: document overflow ${JSON.stringify(layout)}`)
  assert.ok(layout.panel.left >= -1 && layout.panel.right <= width + 1, `${width} ${name}: panel out of viewport ${JSON.stringify(layout)}`)
}
async function chooseTomorrow(page) {
  const day = new Date(Date.now() + 8 * 3600000 + 24 * 3600000).toISOString().slice(0, 10)
  await page.locator('[aria-controls="departure-calendar"]').click()
  const choice = page.locator(`[data-date="${day}"]`)
  if (!await choice.isVisible()) await page.getByRole('button', { name: 'Next month', exact: true }).click()
  await choice.click(); await page.getByLabel('Departure time HKT', { exact: true }).fill('08:20')
}
async function transitionAnimations(page) {
  return page.evaluate(() => document.getAnimations().filter(animation => animation.effect?.pseudoElement?.startsWith('::view-transition')).map(animation => ({ name: animation.animationName, pseudo: animation.effect.pseudoElement, target: animation.effect.target?.tagName, currentTime: animation.currentTime, duration: animation.effect.getTiming().duration, playState: animation.playState })))
}
async function armPageMotion(page, from, to) {
  // Start inside the browser before the real click. A slow automation response
  // must not erase a short animation that the browser has already painted.
  await page.evaluate(({ from, to }) => {
    window.layoutMotionSampler?.cancel()
    const main = document.querySelector('main'), initialScreen = main?.getAttribute('data-screen')
    const sample = { from, to, initialScreen, changedAt: null, frames: [], done: false }
    const armedAt = performance.now()
    let raf, observer
    const stop = () => { cancelAnimationFrame(raf); observer.disconnect(); sample.done = true }
    window.layoutMotionSampler = { sample, cancel: stop }
    observer = new MutationObserver(() => {
      if (sample.changedAt === null && main?.getAttribute('data-screen') !== initialScreen) sample.changedAt = performance.now()
    })
    observer.observe(main, { attributes: true, attributeFilter: ['data-screen'] })
    const tick = now => {
      const screen = main.getAttribute('data-screen')
      if (sample.changedAt === null && screen !== initialScreen) sample.changedAt = now
      if (sample.changedAt !== null) {
        const panels = Array.from(main.querySelectorAll('[data-panel]')).filter(panel => {
          const rect = panel.getBoundingClientRect(), style = getComputedStyle(panel)
          return rect.width > 0 && rect.height > 0 && !panel.closest('[hidden]') && style.visibility !== 'hidden' && style.display !== 'none'
        }).map(panel => { const style = getComputedStyle(panel); return { opacity: Number(style.opacity), transform: style.transform } })
        const animations = document.getAnimations().filter(animation => animation.effect?.pseudoElement?.startsWith('::view-transition') && animation.playState === 'running')
          .map(animation => ({ name: animation.animationName, pseudo: animation.effect.pseudoElement, target: animation.effect.target?.tagName,
            currentTime: animation.currentTime, duration: animation.effect.getTiming().duration, playState: animation.playState }))
        sample.frames.push({ elapsed: now - sample.changedAt, screen, panels, animations })
        if (now - sample.changedAt >= 600) { stop(); return }
      }
      // Bound a missing navigation as well as the post-commit capture window.
      if (now - armedAt >= 3500) { stop(); return }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
  }, { from, to })
}
async function observePageMotion(page, scoped, duringTransition = false) {
  await page.waitForFunction(({ scoped, duringTransition }) => {
    const sample = window.layoutMotionSampler?.sample
    if (!sample) return false
    return sample.done || duringTransition && sample.frames.some(frame => scoped ? frame.animations.length > 0
      : frame.panels.some(panel => panel.opacity < .999 || panel.transform !== 'none'))
  }, { scoped, duringTransition }, { timeout: 4500 })
  const sample = await page.evaluate(() => window.layoutMotionSampler.sample)
  const diagnostic = `${sample.from} → ${sample.to}: ${JSON.stringify(sample)}`
  // Save each transition immediately, so a later assertion failure still keeps
  // all actual frame samples in the CI evidence artifact.
  const name = `${sample.from}-to-${sample.to}${duringTransition ? '-interrupted' : ''}`.toLowerCase().replaceAll(' ', '-')
  fs.writeFileSync(path.join(folder, `motion-${name}.json`), JSON.stringify(sample, null, 2) + '\n')
  assert.ok(sample.changedAt !== null && sample.frames.length > 0, `Navigation was not painted: ${diagnostic}`)
  if (scoped) {
    const animations = sample.frames.flatMap(frame => frame.animations)
    assert.ok(animations.some(animation => Number(animation.duration) >= 200 && Number(animation.duration) <= 500), `Native scope motion timing ${diagnostic}`)
    assert.ok(animations.every(animation => animation.target === 'MAIN'), `Native animations must stay inside the main element scope: ${diagnostic}`)
    return { mode: 'element-scoped', ...sample }
  }
  const moving = sample.frames.filter(frame => frame.panels.some(panel => panel.opacity < .999 || panel.transform !== 'none'))
  assert.ok(moving.length > 0, `Compatible panel motion was not painted: ${diagnostic}`)
  const settledFrame = sample.frames.find(frame => frame.elapsed > moving.at(-1).elapsed && frame.panels.length && frame.panels.every(panel => panel.opacity >= .999 && panel.transform === 'none'))
  return { mode: 'panel-motion', paintedUntil: moving.at(-1).elapsed, settledAt: settledFrame?.elapsed ?? null, ...sample }
}
async function paintDiagnostics(page) {
  return page.evaluate(() => {
    const describe = element => {
      const style = getComputedStyle(element), rect = element.getBoundingClientRect()
      return { tag: element.tagName, class: element.getAttribute('class'), text: element.textContent?.slice(0, 120), style: element.getAttribute('style'), width: rect.width, height: rect.height,
        display: style.display, visibility: style.visibility, opacity: style.opacity, color: style.color, transform: style.transform,
        stroke: style.stroke, fill: style.fill, strokeOpacity: style.strokeOpacity, fillOpacity: style.fillOpacity }
    }
    const map = document.querySelector('[data-map-layer-mode]'), ancestors = []
    for (let element = map; element; element = element.parentElement) ancestors.push(describe(element))
    return { screen: document.querySelector('main')?.getAttribute('data-screen'), ready: document.readyState, documentHidden: document.hidden, motion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      navigationTrace: window.layoutNavigationTrace ?? [], mapAncestors: ancestors,
      animations: document.getAnimations().map(animation => ({ name: animation.animationName, state: animation.playState, time: animation.currentTime, pseudo: animation.effect?.pseudoElement, target: animation.effect?.target?.getAttribute?.('class') })),
      paths: Array.from(document.querySelectorAll('#journey-map .leaflet-overlay-pane svg path')).map(element => ({ ...describe(element), d: element.getAttribute('d') })),
      mapPanes: Array.from(document.querySelectorAll('#journey-map, #journey-map .leaflet-pane, #journey-map svg, [data-panel]')).map(describe),
      stationLabels: Array.from(document.querySelectorAll('#journey-map .leaflet-tooltip, #journey-map .leaflet-tooltip span')).map(describe),
      fonts: { status: document.fonts.status, loaded: Array.from(document.fonts).map(font => ({ family: font.family, status: font.status })) } }
  })
}
async function rects(page) {
  return page.evaluate(() => {
    const rect = element => { const r = element?.getBoundingClientRect(); return r && { left: r.left, top: r.top, width: r.width, height: r.height, right: r.right, bottom: r.bottom } }
    const panel = Array.from(document.querySelectorAll('[data-panel]')).find(element => element.getBoundingClientRect().width > 0 && element.getBoundingClientRect().height > 0)
    return { panel: rect(panel), map: rect(document.getElementById('journey-map')), viewport: innerWidth, document: document.documentElement.scrollWidth }
  })
}
function pass(name) { checks.push(name); console.log('PASS ' + name) }
let browser, page
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
  if (process.env.LAYOUT_FORCE_FALLBACK === '1') await context.addInitScript(() => Object.defineProperty(Element.prototype, 'startViewTransition', { configurable: true, value: undefined }))
  // Basemap reads may render for screenshots; all application writes stay local.
  await context.route('**/*', route => {
    const request = route.request(), url = request.url()
    const local = url.startsWith(web) || url.startsWith(api)
    const mapRead = request.method() === 'GET' && /^https:\/\/(tiles\.openfreemap\.org|tile\.openstreetmap\.org|[^/]*\.basemaps\.cartocdn\.com)\//.test(url)
    return local || mapRead ? route.continue() : route.abort()
  })
  page = await context.newPage(); page.setDefaultTimeout(15000)
  page.on('pageerror', error => browserErrors.push(error.message))
  const applicationWrites = []
  page.on('request', request => { if (request.method() === 'POST') { assert.ok(request.url().startsWith(api), 'Application write escaped isolated API'); applicationWrites.push(new URL(request.url()).pathname) } })
  await page.goto(web + '?view=planner'); await page.getByRole('button', { name: 'Find resilient routes', exact: false }).waitFor()
  await assertRemovedPages(page); await settled(page)
  // Let the remote basemap finish its first paint for review screenshots. The
  // assertions below still work if that optional geographic background fails.
  await page.waitForResponse(response => /^https:\/\/(tiles\.openfreemap\.org\/planet\/.+\.(pbf|mvt)|tile\.openstreetmap\.org\/.+\.png)/.test(response.url()) && response.ok(), { timeout: 8000 }).catch(() => {})
  await pause(500); await frames(page)
  const layouts = {}
  for (const width of [1440, 1024]) {
    await page.setViewportSize({ width, height: 1000 }); layouts[width] = {}
    for (const name of ['Plan journey', 'Report', 'Agent']) {
      await navigate(page, name); await settled(page)
      layouts[width][name] = await rects(page)
      if (width === 1440) await page.screenshot({ path: path.join(folder, name.toLowerCase().replaceAll(' ', '-') + '-1440.png') })
      if (!baseline) {
        const current = layouts[width][name], journey = layouts[width]['Plan journey']
        for (const key of ['left', 'top', 'width', 'height']) assert.ok(Math.abs(current.panel[key] - journey.panel[key]) <= 1, `${width} ${name} ${key}: ${JSON.stringify(current)}`)
        assert.ok(current.map.left >= current.panel.right + 20, `${name}: map covered by panel ${JSON.stringify(current)}`)
        assert.ok(current.map.width > 200 && current.map.height > 400, `${name}: map lacks useful viewport`)
      }
    }
  }
  fs.writeFileSync(path.join(folder, 'layout-evidence.json'), JSON.stringify({ baseline, layouts, browserErrors }, null, 2) + '\n')
  if (baseline) { console.log(JSON.stringify({ baseline: true, layouts, folder })); return }
  pass('1440 and 1024: Journey, Report and Agent share the same sidebar and adjacent map geometry')
  await page.setViewportSize({ width: 1440, height: 1000 }); await navigate(page, 'Plan journey'); await settled(page)
  // ResizeObserver refits Leaflet after the panel settles; wait for the
  // station geometry itself instead of assuming the 300 ms UI delay paints it.
  await page.waitForFunction(() => Array.from(document.querySelectorAll('#journey-map .leaflet-overlay-pane svg path'))
    .filter(path => /a/i.test(path.getAttribute('d') ?? '') && Number(getComputedStyle(path).strokeOpacity) > 0).length >= 6)
  const defaultPaths = await mapPaths(page), stations = defaultPaths.filter(path => /a/i.test(path.d))
  assert.equal(defaultPaths.filter(path => !/a/i.test(path.d)).length, 0, 'Default map unexpectedly draws route/network lines')
  assert.ok(stations.length >= 6, 'Default map should retain station markers')
  assert.ok(stations.every(station => contrast(station.stroke, station.fill) < 3), 'Default station markers should use low contrast strokes')
  pass('default map retains subtle station markers and draws no network paths')
  await page.getByRole('combobox', { name: 'TO', exact: true }).click()
  await page.getByRole('option', { name: /^Admiralty East Rail/ }).click(); await chooseTomorrow(page)
  const routeReply = page.waitForResponse(response => response.url() === api + '/api/routes/query' && response.ok())
  await page.getByRole('button', { name: 'Find resilient routes' }).click()
  const actualRoutes = await (await routeReply).json(); await page.getByRole('heading', { name: 'Tai Wai → Admiralty' }).waitFor(); await settled(page)
  assert.ok(actualRoutes.length > 0)
  assert.deepEqual(await page.locator('[data-route-id]').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-route-id'))), actualRoutes.map(route => route.route_id))
  assert.ok((await mapPaths(page)).some(path => !/a/i.test(path.d)), 'Route search should draw actual candidate paths')
  await page.screenshot({ path: path.join(folder, 'candidate-routes-1440.png') })
  pass('real route query displays returned candidates and draws their journey geometry')
  await navigate(page, 'Agent'); await settled(page)
  const draft = 'Retain this unsent draft during navigation'
  await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').fill(draft)
  await navigate(page, 'Updates'); await settled(page); await navigate(page, 'How it works'); await settled(page); await navigate(page, 'Agent'); await settled(page)
  assert.equal(await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').inputValue(), draft)
  pass('Agent stays mounted and preserves its unsent draft through Updates and How it works')
  // Use protected fixture setup only on the temporary m2_server database. The
  // passenger browser still receives the real approved facts through polling.
  const reportText = '【模拟布局浏览器测试】东铁线红磡至会展信号故障，暂停服务。'
  const signal = await call('/api/signals', { raw_text: reportText, author_hint: 'layout-browser-1' })
  const draftEvent = (await call('/api/events/ingest', { signal_id: signal.signal_id }, true)).draft
  const now = new Date().toISOString(), end = new Date(Date.now() + 48 * 3600000).toISOString()
  const event = await call('/api/events', { event_id: 'layout-browser-disruption', version: 1, status: 'pending_review', created_at: now, updated_at: now, published_at: null, expires_at: null,
    event_type: draftEvent.event_type, title: draftEvent.title, summary: draftEvent.summary, mode: draftEvent.mode, line: draftEvent.line, direction: 'both',
    affected_segments: draftEvent.affected_segments.map(segment => ({ ...segment, capacity_factor: 0 })), window: { start: new Date(Date.now() - 60000).toISOString(), end, end_confidence: 'local-test-window' },
    severity: 4, confidence: 0, confidence_factors: [], signals: [signal.signal_id], reviewed_by: null, audit_log: [], provenance: 'simulated' }, true)
  for (const author of ['layout-browser-2', 'layout-browser-3']) {
    const nextSignal = await call('/api/signals', { raw_text: reportText, author_hint: author })
    assert.equal((await call('/api/events/ingest', { signal_id: nextSignal.signal_id }, true)).state, 'merged')
  }
  const approved = await call(`/api/events/${event.event_id}/review`, { action: 'approve', actor: 'isolated-layout-browser' }, true)
  await navigate(page, 'Plan journey'); await page.locator(`[data-event-revisions*="${event.event_id}@${approved.version}"]`).waitFor(); await settled(page)
  assert.equal((await mapPaths(page)).filter(path => !/a/i.test(path.d)).length, 0, 'Approved events must not reintroduce background lines on the default planner')
  await navigate(page, 'Report'); await settled(page)
  assert.equal((await mapPaths(page)).filter(path => !/a/i.test(path.d)).length, 0)
  await navigate(page, 'Agent'); await settled(page)
  assert.equal((await mapPaths(page)).filter(path => !/a/i.test(path.d)).length, 0)
  await navigate(page, 'Updates'); await page.getByRole('heading', { name: approved.title, exact: true }).waitFor(); await settled(page)
  assert.ok((await mapPaths(page)).some(path => !/a/i.test(path.d) && path.dash !== 'none'), 'Updates map should still identify approved impacts')
  await page.screenshot({ path: path.join(folder, 'updates-approved-event-1440.png') })
  pass('approved updates remain visible while Journey, Report and Agent backgrounds stay free of disruption lines')
  const mobileLayouts = {}
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 }); mobileLayouts[width] = {}
    for (const name of ['Plan journey', 'Report', 'Agent', 'Updates', 'How it works']) {
      await navigate(page, name); await settled(page); await noOverflow(page, name, width)
      mobileLayouts[width][name] = await rects(page)
      if (name === 'Report') {
        await page.getByLabel('What did you see?', { exact: true }).fill('Local layout test; no report is submitted.')
        await page.getByLabel('Source hint (optional)', { exact: true }).fill('local-only')
        await page.getByRole('button', { name: /Send unverified report/ }).scrollIntoViewIfNeeded()
        assert.ok(await page.getByRole('button', { name: /Send unverified report/ }).isVisible())
        assert.ok(await page.getByRole('button', { name: /Send unverified report/ }).isEnabled())
      } else if (name === 'Agent') {
        await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').fill(draft)
        await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').press('Tab')
        assert.equal(await page.getByRole('button', { name: 'Send message', exact: true }).evaluate(button => document.activeElement === button), true)
      } else if (name === 'Plan journey') {
        await page.getByRole('button', { name: 'Find resilient routes' }).scrollIntoViewIfNeeded()
        assert.ok(await page.getByRole('button', { name: 'Find resilient routes' }).isVisible())
        await page.getByRole('tab', { name: 'Map', exact: true }).click(); await settled(page)
        const stationLabel = page.locator('#journey-map .leaflet-tooltip').filter({ hasText: 'Tai Wai' }).first()
        await stationLabel.waitFor({ state: 'visible' })
        // Leaflet can reveal the tooltip box before its text after a hidden-map
        // resize/fit. Wait for the actual English text paint, with a short bound.
        await stationLabel.getByText('Tai Wai', { exact: true }).waitFor({ state: 'visible', timeout: 1500 })
        assert.ok((await stationLabel.innerText()).includes('Tai Wai'), 'Mobile map should paint the English station label')
        if (width === 390) await page.screenshot({ path: path.join(folder, 'journey-map-390.png') })
        await page.getByRole('tab', { name: 'Journey', exact: true }).click(); await settled(page)
      }
      if (width === 390) await page.screenshot({ path: path.join(folder, name.toLowerCase().replaceAll(' ', '-') + '-390.png') })
    }
  }
  pass('390 and 320: all five retained pages fit; Report form actions and Agent composer remain reachable by keyboard')
  pass('390 and 320: the revealed journey map retains visible English station labels')
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.emulateMedia({ reducedMotion: 'no-preference' }); await frames(page)
  const scopedCapability = await page.evaluate(() => typeof document.querySelector('main').startViewTransition === 'function')
  console.log('Scoped transition capability: ' + scopedCapability)
  const motions = []
  for (const from of ['Plan journey', 'Report', 'Agent']) for (const to of ['Updates', 'How it works']) {
    await navigate(page, from); await settled(page)
    await armPageMotion(page, from, to)
    await navigate(page, to)
    const observed = await observePageMotion(page, scopedCapability)
    motions.push({ from, to, ...observed })
    if (from === 'Plan journey') await page.screenshot({ path: path.join(folder, 'transition-' + to.toLowerCase().replaceAll(' ', '-') + '-1440.png'), animations: 'allow' })
    await settled(page)
  }
  pass(scopedCapability ? 'all six requested page changes render measured element-scoped outgoing/incoming animations' : 'all six requested page changes paint compatible panel motion without document snapshots')
  // Real pointer clicks on visible header controls occur before the previous
  // snapshots finish; no forced click or hidden element is used.
  await page.evaluate(() => {
    window.layoutNavigationTrace = []
    for (const kind of ['pointerdown', 'pointerup', 'click']) document.addEventListener(kind, event => {
      const button = event.target instanceof Element ? event.target.closest('#main-navigation button') : null
      window.layoutNavigationTrace.push({ kind, button: button?.textContent, target: event.target instanceof Element ? event.target.tagName : '', trusted: event.isTrusted,
        screen: document.querySelector('main')?.getAttribute('data-screen'), time: performance.now() })
    }, { capture: true })
  })
  const rapidNames = ['Plan journey', 'Updates', 'How it works', 'Report', 'Agent'], rapidBoxes = []
  for (const name of rapidNames) {
    const button = page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name, exact: true })
    assert.ok(await button.isVisible())
    rapidBoxes.push(await button.boundingBox())
  }
  for (const box of rapidBoxes) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
  await settled(page)
  const rapidTrace = await page.evaluate(() => ({ screen: document.querySelector('main')?.getAttribute('data-screen'), events: window.layoutNavigationTrace }))
  fs.writeFileSync(path.join(folder, 'rapid-navigation-trace.json'), JSON.stringify(rapidTrace, null, 2) + '\n')
  assert.deepEqual(rapidTrace.events.filter(event => event.kind === 'click' && event.trusted).map(event => event.button), rapidNames, 'Every rapid header pointer click must reach its actual visible button')
  await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').fill('Latest navigation remains interactive')
  assert.equal(await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').inputValue(), 'Latest navigation remains interactive')
  assert.equal((await transitionAnimations(page)).length, 0, 'Interrupted navigation left a transition overlay')
  assert.equal(await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: 'Agent', exact: true }).getAttribute('aria-current'), 'page')
  pass('rapid navigation settles on the last page, with interactive controls and no orphan transition overlay')
  await navigate(page, 'Plan journey'); await settled(page)
  await armPageMotion(page, 'Plan journey', 'Report'); await navigate(page, 'Report')
  await observePageMotion(page, scopedCapability, true)
  await page.emulateMedia({ reducedMotion: 'reduce' }); await frames(page)
  await page.getByLabel('What did you see?', { exact: true }).fill('Reduced motion enabled during the page transition.')
  await settled(page); assert.equal((await transitionAnimations(page)).length, 0)
  pass('enabling reduced motion during an active transition immediately leaves the selected Report form interactive')
  // Delay the real browser snapshot callback to exercise a preference change
  // before the new DOM has committed, rather than only after its first frame.
  if (scopedCapability) {
    await page.emulateMedia({ reducedMotion: 'no-preference' }); await frames(page)
    await navigate(page, 'Plan journey'); await settled(page)
    await page.evaluate(() => {
      const surface = document.querySelector('main'), nativeTransition = surface.startViewTransition.bind(surface)
      Object.defineProperty(surface, 'startViewTransition', { configurable: true, value: argument => nativeTransition(() => new Promise(resolve => {
        const update = typeof argument === 'function' ? argument : argument.update ?? argument.callback
        window.releaseLayoutSnapshot = () => { update(); resolve() }
      })) })
    })
    await navigate(page, 'Updates')
    await page.waitForFunction(() => typeof window.releaseLayoutSnapshot === 'function')
    assert.equal(await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name: 'Plan journey', exact: true }).getAttribute('aria-current'), 'page')
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.getByRole('heading', { name: 'What we know.', exact: true }).waitFor({ timeout: 1200 })
    await page.evaluate(() => { window.releaseLayoutSnapshot(); delete window.releaseLayoutSnapshot; delete document.querySelector('main').startViewTransition })
    await settled(page); assert.equal((await transitionAnimations(page)).length, 0)
    pass('a reduced-motion change before the native snapshot callback commits the latest navigation immediately')
  } else console.log('Scoped snapshots unavailable; compatibility motion and immediate navigation are verified instead of the native pending-callback case')
  await page.emulateMedia({ reducedMotion: 'reduce' }); await frames(page)
  for (const from of ['Plan journey', 'Report', 'Agent']) for (const to of ['Updates', 'How it works']) {
    await navigate(page, from); await navigate(page, to); await frames(page)
    assert.equal((await transitionAnimations(page)).length, 0, 'Reduced motion created a page transition')
    const visiblePanels = await page.locator('[data-panel]').evaluateAll(panels => panels.filter(panel => panel.getBoundingClientRect().width > 0).map(panel => ({ opacity: getComputedStyle(panel).opacity, transform: getComputedStyle(panel).transform })))
    assert.ok(visiblePanels.every(panel => panel.opacity === '1' && panel.transform === 'none'), 'Reduced motion left an animated panel style')
  }
  pass('reduced motion skips all six page transitions and leaves visible panels fully opaque')
  await page.emulateMedia({ reducedMotion: 'no-preference' }); await frames(page)
  await page.evaluate(() => Object.defineProperty(document.querySelector('main'), 'startViewTransition', { configurable: true, value: undefined }))
  await navigate(page, 'Plan journey'); await settled(page); await navigate(page, 'How it works'); await settled(page)
  await page.getByRole('heading', { name: 'Clarity before certainty.' }).waitFor()
  assert.equal((await transitionAnimations(page)).length, 0)
  await armPageMotion(page, 'How it works', 'Report'); await navigate(page, 'Report'); await observePageMotion(page, false); await settled(page)
  await page.getByLabel('What did you see?', { exact: true }).fill('Older browsers retain usable navigation.')
  assert.equal(await page.getByLabel('What did you see?', { exact: true }).inputValue(), 'Older browsers retain usable navigation.')
  const fallbackPanels = await page.locator('[data-panel]').evaluateAll(panels => panels.filter(panel => panel.getBoundingClientRect().width > 0).map(panel => ({ opacity: getComputedStyle(panel).opacity, transform: getComputedStyle(panel).transform })))
  assert.ok(fallbackPanels.every(panel => panel.opacity === '1' && panel.transform === 'none'), 'Unsupported-browser fallback left an animated panel style')
  await page.evaluate(() => window.layoutNavigationTrace = [])
  for (const box of rapidBoxes) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
  await settled(page)
  const fallbackRapid = await page.evaluate(() => ({ screen: document.querySelector('main').dataset.screen, events: window.layoutNavigationTrace }))
  assert.deepEqual(fallbackRapid.events.filter(event => event.kind === 'click' && event.trusted).map(event => event.button), rapidNames)
  assert.equal(fallbackRapid.screen, 'agent')
  await page.getByLabel('ASK ABOUT THE CURRENT JOURNEY').fill('Fallback fast navigation remains usable')
  await page.evaluate(() => delete document.querySelector('main').startViewTransition)
  pass('browsers without scoped View Transitions paint panel motion, accept input and deliver every rapid header click')
  assert.deepEqual(browserErrors, [])
  assert.ok(applicationWrites.length > 0 && applicationWrites.every(endpoint => endpoint === '/api/routes/query'), 'Passenger browser must not send Reports or AI chat during layout acceptance')
  fs.writeFileSync(path.join(folder, 'layout-evidence.json'), JSON.stringify({ passed: true, checks, scopedCapability, layouts, mobileLayouts, defaultStationCount: stations.length, defaultStationContrast: stations.map(station => contrast(station.stroke, station.fill)), routeIds: actualRoutes.map(route => route.route_id), approvedEvent: { id: approved.event_id, version: approved.version, title: approved.title }, motions, rapidTrace, fallbackRapid, browserErrors, applicationWrites }, null, 2) + '\n')
  console.log(JSON.stringify({ passed: true, checks: checks.length, folder }))
})().catch(async error => {
  console.error(error.stack)
  if (page) {
    console.error((await page.locator('body').innerText().catch(() => '')).slice(-6000))
    const initial = await paintDiagnostics(page).catch(cause => ({ error: String(cause) }))
    await page.screenshot({ path: path.join(folder, 'failure.png') }).catch(() => {})
    await pause(750); await frames(page)
    const later = await paintDiagnostics(page).catch(cause => ({ error: String(cause) }))
    fs.writeFileSync(path.join(folder, 'failure-diagnostics.json'), JSON.stringify({ error: error.stack, initial, later }, null, 2) + '\n')
    await page.screenshot({ path: path.join(folder, 'failure-later.png') }).catch(() => {})
  }
  for (const child of children) if (child.exitCode !== null) console.error(child.logs())
  process.exitCode = 1
}).finally(async () => {
  await browser?.close()
  for (const child of children) if (child.exitCode === null) {
    if (process.platform === 'win32') await new Promise(resolve => spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }).on('exit', resolve))
    else child.kill('SIGTERM')
  }
})
