// Validate decoding and seekable duration of the actual checked-in fallback video.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict')
const { pathToFileURL } = require('node:url')
const { chromium } = require(process.env.M2_PLAYWRIGHT || 'playwright')
const root = path.resolve(__dirname, '../..'), out = path.join(root, '.cache/p4-media')
fs.mkdirSync(out, { recursive: true })
const evidence = { environment: process.env.CI ? 'CI media decoder' : 'local media decoder', passed: false, samples: [] }
let browser
;(async () => {
  browser = await chromium.launch({ headless: true, ...(process.env.M2_BROWSER_CHANNEL ? { channel: process.env.M2_BROWSER_CHANNEL } : {}) })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.goto(pathToFileURL(path.join(root, 'deploy/offline/media/demo.webm')).href)
  await page.locator('video').waitFor()
  await page.waitForFunction(() => document.querySelector('video').readyState >= 2)
  evidence.duration_seconds = await page.locator('video').evaluate(video => video.duration)
  assert.ok(Number.isFinite(evidence.duration_seconds) && evidence.duration_seconds >= 299 && evidence.duration_seconds <= 330)
  for (const seconds of [30, 90, 150, 210, 285]) {
    const result = await page.locator('video').evaluate(async (video, time) => {
      await new Promise((resolve, reject) => {
        video.addEventListener('seeked', resolve, { once: true })
        video.addEventListener('error', () => reject(new Error('Media decode failed')), { once: true })
        video.currentTime = time
      })
      await video.play(); await new Promise(resolve => setTimeout(resolve, 100)); video.pause()
      return { seconds: time, width: video.videoWidth, height: video.videoHeight, error: video.error?.code || null,
        decoded_frames: video.getVideoPlaybackQuality().totalVideoFrames }
    }, seconds)
    assert.equal(result.error, null); assert.ok(result.width > 0 && result.height > 0 && result.decoded_frames > 0)
    evidence.samples.push(result); await page.screenshot({ path: path.join(out, `frame-${seconds}.png`) })
  }
  evidence.passed = true
})().catch(error => { evidence.error = error.stack; process.exitCode = 1 }).finally(async () => {
  await browser?.close(); fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify(evidence, null, 2)); console.log(JSON.stringify(evidence))
})
