// Independent onboarding regression: a production build, no backend required.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const { chromium } = require(process.env.M2_PLAYWRIGHT || 'playwright')
const axeSource = fs.readFileSync(require.resolve('axe-core', { paths: [path.dirname(require.resolve(process.env.M2_PLAYWRIGHT || 'playwright'))] }), 'utf8')
const root = path.resolve(__dirname, '../..'), out = path.join(root, '.cache/preferences-browser')
const suppliedUrl = process.env.PREFERENCES_WEB_URL
const web = suppliedUrl || 'http://127.0.0.1:5187'
let server, browser, logs = ''
const errors = [], evidence = { passed: false, dimensions: [], assertions: [] }
fs.mkdirSync(out, { recursive: true })
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
const state = page => page.evaluate(() => JSON.parse(localStorage.getItem('rr.preferences.v1')))
const profile = page => page.evaluate(() => JSON.parse(localStorage.getItem('rr.weight-profile.v1')))
async function audit(page, label) {
  await page.waitForFunction(() => [...document.querySelectorAll('[data-content],[data-stagger],[data-map-feedback]')].every(element => Number(getComputedStyle(element).opacity) > .99))
  await page.addScriptTag({ content: axeSource })
  const violations = await page.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa'] } })).violations.map(item => ({ id:item.id, impact:item.impact, nodes:item.nodes.map(node => node.target) })))
  assert.deepEqual(violations, [], `${label} must satisfy automated WCAG AA checks`)
}
async function ready() {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (server?.exitCode != null) throw new Error('Preview stopped: ' + logs)
    try { if ((await fetch(web)).ok) return } catch {}
    await pause(100)
  }
  throw new Error('Preview did not become ready: ' + logs)
}
async function choose(page, index = 0) {
  await page.getByRole('radio').nth(index).click()
  await page.waitForFunction(() => !JSON.parse(localStorage.getItem('rr.preferences.v1')).pending && !document.querySelector('[role="radiogroup"]'))
}
;(async () => {
  if (!suppliedUrl) {
    server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '5187', '--strictPort'], { cwd: path.join(root, 'frontend'), windowsHide: true, stdio: ['ignore','pipe','pipe'] })
    server.stdout.on('data', chunk => logs += chunk); server.stderr.on('data', chunk => logs += chunk)
    server.on('error', error => logs += error.message)
  }
  await ready()
  browser = await chromium.launch({ headless: true, ...(process.env.M2_BROWSER_CHANNEL ? { channel: process.env.M2_BROWSER_CHANNEL } : {}) })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error' && !message.text().includes('fonts.googleapis')) errors.push(message.text()) })
  await page.goto(web)
  await page.getByRole('button', { name: '开始认识我的偏好' }).waitFor()
  await audit(page, 'Welcome')
  await page.screenshot({ path: path.join(out,'welcome.png'), fullPage: true })
  await page.getByRole('button', { name: '开始认识我的偏好' }).click()
  await page.getByRole('heading', { name: '快一点，还是从容一点？' }).waitFor()
  await audit(page, 'Question')
  assert.equal(await page.locator('[data-dimension]').getAttribute('data-dimension'), 'time')
  const start = Date.now()
  await page.getByRole('radio').nth(0).click()
  await page.getByRole('heading', { name: '关于换乘，你怎么想？' }).waitFor()
  assert.ok(Date.now() - start >= 600, 'automatic transition must leave time for feedback')
  await page.getByRole('button', { name: '暂时跳过' }).click()
  assert.equal((await state(page)).answers.transfers, null)
  await page.getByRole('button', { name: '上一题' }).click()
  assert.equal(await page.getByRole('radio').count(), 3)
  await page.getByRole('radio').nth(1).press('ArrowDown')
  assert.equal(await page.evaluate(() => document.activeElement.dataset.option), '2')
  await page.getByRole('radio').nth(2).press('Enter')
  await page.getByRole('heading', { name: '准时这件事，有多重要？' }).waitFor()
  await choose(page, 1)
  assert.equal((await state(page)).phase, 'summary')
  assert.equal((await profile(page)).collected, 3)
  await audit(page, 'Summary')
  await page.screenshot({ path: path.join(out,'summary.png'), fullPage: true })
  await page.getByRole('button', { name: '回看答案' }).click()
  assert.equal(await page.getByRole('radio').nth(1).getAttribute('aria-checked'), 'true')
  await page.getByRole('radio').nth(0).press('Escape')
  assert.equal((await profile(page)).evidence.reliability.status, 'prior')
  assert.equal((await state(page)).answers.reliability, 'reliability-1')
  await page.reload()
  assert.equal(await page.getByRole('radio').nth(2).getAttribute('aria-checked'), 'true')
  await page.getByRole('button', { name: '保留并继续' }).click()
  await page.getByRole('button', { name: '保留并继续' }).click()
  await page.getByRole('button', { name: '继续完善' }).click()
  await audit(page, 'Library')
  const additional = [['碳排放','carbon'],['信息新鲜度','freshness'],['无障碍友好','accessibility'],['步行距离','walking'],['出行票价','fare'],['乘坐舒适','comfort']]
  for (const [label, dimension] of additional) {
    await page.getByRole('button', { name: new RegExp(label) }).click()
    assert.equal(await page.locator('[data-dimension]').getAttribute('data-dimension'), dimension)
    await choose(page)
    evidence.dimensions.push(dimension)
  }
  await page.getByRole('button', { name: '完成，保存我的偏好' }).click()
  const completed = await profile(page)
  assert.equal(completed.collected, 9)
  assert.equal(completed.completed, true)
  await audit(page, 'Complete')
  assert.ok(Math.abs(Object.values(completed.weights).reduce((a,b) => a+b,0) - 1) < 1e-12)
  const events = await page.evaluate(() => JSON.parse(localStorage.getItem('rr.preference-events.v1')).map(item => item.event))
  for (const event of ['start','answer','skip','back','continue','complete']) assert.ok(events.includes(event))
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出画像' }).click()
  const result = await download
  await result.saveAs(path.join(out,'profile.json'))
  assert.equal(JSON.parse(fs.readFileSync(path.join(out,'profile.json'))).collected,9)
  const mobile = await browser.newContext({ viewport: { width: 375, height: 812 }, reducedMotion: 'reduce' })
  const mobilePage = await mobile.newPage()
  mobilePage.on('pageerror', error => errors.push(error.message))
  await mobilePage.goto(web)
  await mobilePage.getByRole('button', { name: '开始认识我的偏好' }).waitFor()
  const layout = await mobilePage.evaluate(() => {
    const left = document.querySelector('#preference-content').getBoundingClientRect()
    const right = document.querySelector('aside').getBoundingClientRect()
    return { stacked: right.top >= left.bottom, overflow: document.documentElement.scrollWidth > innerWidth, animations: document.getAnimations().filter(animation => animation.playState === 'running').length }
  })
  assert.equal(layout.stacked, true); assert.equal(layout.overflow, false); assert.equal(layout.animations, 0)
  await mobilePage.screenshot({ path: path.join(out,'mobile.png'), fullPage: true })
  await mobilePage.getByRole('button', { name: '开始认识我的偏好' }).click()
  for (let i=0;i<3;i++) await mobilePage.getByRole('button', { name: '暂时跳过' }).click()
  assert.equal((await profile(mobilePage)).collected,0)
  await mobilePage.getByRole('button', { name: '完成，保存我的偏好' }).click()
  assert.equal((await profile(mobilePage)).completed,true)
  assert.deepEqual(errors,[])
  evidence.assertions = ['750ms advance','skip and back','keyboard arrows Enter Escape','history and reload','nine dimensions','unit-sum weights','event tracking','JSON export','375px stacked layout','reduced motion','all skipped fallback','WCAG AA five phases','no console errors']
  evidence.passed = true
  console.log(JSON.stringify(evidence,null,2))
})().catch(error => { evidence.error = error.stack; console.error(error); process.exitCode=1 }).finally(async () => {
  fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2))
  await browser?.close(); server?.kill()
})
