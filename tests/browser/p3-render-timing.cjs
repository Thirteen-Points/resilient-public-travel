// Timing ends after a rendered map revision / real route-card DOM and two frames.
// API arrival alone is not acceptance. Caller records every attempted round.
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
async function until(check, timeout = 20000) {
  const started = performance.now()
  while (performance.now() - started < timeout) { if (await check()) return; await pause(25) }
  throw new Error('Rendered state timed out')
}
async function frames(page) { await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))) }
async function mapPainted(page) {
  return page.locator('.leaflet-overlay-pane').evaluate(pane => {
    if (pane.querySelector('svg path[d]')) return true
    return Array.from(pane.querySelectorAll('canvas')).some(canvas => {
      if (!canvas.width || !canvas.height) return false
      const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data
      for (let i = 3; i < pixels.length; i += 16) if (pixels[i]) return true
      return false
    })
  })
}
async function futureJourney(page) {
  const value = new Date(Date.now() + 8 * 3600000 + 10 * 60000).toISOString().slice(0, 16)
  await page.locator('[aria-controls="departure-calendar"]').click()
  const day = page.getByRole('button', { name: new RegExp('^' + value.slice(0, 10)) })
  if (!await day.count()) await page.getByRole('button', { name: 'Next month', exact: true }).click()
  await day.click()
  await page.getByLabel('Departure time HKT', { exact: true }).fill(value.slice(11, 16))
  return value + ':00+08:00'
}
async function publication(visitor, administrator, eventId) {
  const marker = visitor.locator('[data-route-refresh-revision]')
  const previous = Number(await marker.getAttribute('data-route-refresh-revision'))
  const response = administrator.waitForResponse(value => value.url().endsWith(`/events/${eventId}/review`) && value.request().postDataJSON()?.action === 'approve')
  const routesResponse = visitor.waitForResponse(value => value.url().endsWith('/api/routes/query') && value.ok())
  const record = { started_at: new Date().toISOString(), network: 'online; browser not throttled', service: 'warm after health preflight; cold-start not measured', map_ms: null, routes_ms: null, passed: false }
  let started = performance.timeOrigin + performance.now()
  await administrator.getByRole('button', { name: 'Confirm publication', exact: true }).evaluate(button => button.addEventListener('click', () => { window.__p3ConfirmedAt = performance.timeOrigin + performance.now() }, { once: true }))
  try {
    await administrator.getByRole('button', { name: 'Confirm publication', exact: true }).click()
    started = await administrator.evaluate(() => window.__p3ConfirmedAt)
    record.started_at = new Date(started).toISOString()
    const approved = await response
    if (!approved.ok()) throw new Error(`Publication HTTP ${approved.status()}`)
    const event = await approved.json(); record.event_version = event.version
    const observations = await Promise.allSettled([
      (async () => {
        await visitor.locator(`[data-event-revisions*="${eventId}@${event.version}"]`).waitFor({ timeout: 20000 })
        await frames(visitor)
        if (!await mapPainted(visitor)) throw new Error('Map overlay not rendered')
        record.map_ms = Math.round(performance.timeOrigin + performance.now() - started)
      })(),
      (async () => {
        const routeReply = await (await routesResponse).json()
        await until(async () => Number(await marker.getAttribute('data-route-refresh-revision')) > previous)
        const expected = routeReply.slice(0, 3)
        await until(async () => JSON.stringify(await visitor.locator('[data-route-id]').evaluateAll(elements => elements.map(element => element.getAttribute('data-route-id')))) === JSON.stringify(expected.map(route => route.route_id)))
        // Check every visible card against its returned numbers, not a counter alone.
        for (const route of expected) {
          const card = visitor.locator(`[data-route-id="${route.route_id}"]`)
          await card.waitFor({ state: 'visible' })
          const text = await card.innerText()
          if (!text.includes(`${route.total.walk_m} m walk`) || !text.includes(`HK$${route.total.fare_hkd.toFixed(2)}`)) throw new Error('Route-card metrics differ from response')
        }
        await frames(visitor); record.routes_ms = Math.round(performance.timeOrigin + performance.now() - started)
        record.route_ids = expected.map(route => route.route_id)
      })(),
    ])
    const failures = observations.filter(value => value.status === 'rejected')
    if (failures.length) record.error = failures.map(value => value.reason.message).join('; ')
    if (failures.length) record.observed_map_revisions = await visitor.locator('[data-event-revisions]').getAttribute('data-event-revisions')
    record.passed = !failures.length && record.map_ms <= 5000 && record.routes_ms <= 5000
  } catch (error) { record.error = error.message; response.catch(() => {}); routesResponse.catch(() => {}) }
  return record
}
module.exports = { publication, until, frames, futureJourney, mapPainted }
