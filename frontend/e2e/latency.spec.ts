import { type APIRequestContext, expect, test } from '@playwright/test'

/** F6: a new alert is on the guard's screen within 2 s of its event reaching the API. */
const BUDGET_MS = 2000
const API = `${(process.env.E2E_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')}/api/v1`
const CARD = 'article[aria-label*="After-hours entry at s-fence-n"]'

declare global {
  interface Window {
    cardSeenAt?: number
  }
}

interface Named {
  id: string
  code: string
}

async function json<T>(answer: Awaited<ReturnType<APIRequestContext['get']>>): Promise<T> {
  expect(answer.ok(), `${answer.url()} answered ${answer.status()}`).toBe(true)
  return (await answer.json()) as T
}

/**
 * Replaces the community's current run with a fresh S2 (D-77), so this check stops any run in
 * progress. The guard's console follows the empty run; then one after-hours sighting goes in.
 */
test('an alert reaches the guard console within 2 s of its event (M4.7)', async ({
  page,
  playwright,
}) => {
  const api = await playwright.request.newContext()
  const users = await json<Named[]>(await api.get(`${API}/session/users`))
  const supervisor = users.find((user) => user.code === 'u-sup-01')
  expect(supervisor, 'the seeded supervisor').toBeTruthy()
  const session = await json<{ token: string; community_id: string }>(
    await api.post(`${API}/session`, { data: { user_id: supervisor?.id } }),
  )
  const headers = { Authorization: `Bearer ${session.token}` }

  const scenarios = await json<Named[]>(await api.get(`${API}/scenarios`, { headers }))
  const s2 = scenarios.find((scenario) => scenario.code === 's2-night-fence')
  expect(s2, 'the seeded S2 scenario').toBeTruthy()
  const started = await json<{ id: string }>(
    await api.post(`${API}/scenario-runs`, { headers, data: { scenario_id: s2?.id, speed: 1 } }),
  )
  const run = await json<{ id: string; window_start: string }>(
    await api.post(`${API}/scenario-runs/${started.id}/reset`, { headers }),
  )
  const layout = await json<{ nodes: Named[] }>(
    await api.get(`${API}/communities/${session.community_id}/layout`, { headers }),
  )
  const fence = layout.nodes.find((node) => node.code === 's-fence-n')
  expect(fence, 'the back-fence sensor').toBeTruthy()

  await page.goto('/')
  await page.getByRole('button', { name: /Guard C/ }).click()
  await expect(page.getByRole('region', { name: 'Alerts' }).getByText('Live')).toBeVisible()

  // The page notes the moment the card is in the DOM; polling from here would add its own delay.
  await page.evaluate((selector) => {
    const watch = new MutationObserver(() => {
      if (!document.querySelector(selector)) return
      window.cardSeenAt = Date.now()
      watch.disconnect()
    })
    watch.observe(document.body, { childList: true, subtree: true })
  }, CARD)

  const sent = Date.now()
  const event = {
    run_id: run.id,
    // Inside quiet hours: 02:09 in the community's time.
    ts: new Date(Date.parse(run.window_start) + 60_000).toISOString(),
    node_id: fence?.id,
    type: 'appear',
    object_class: 'person',
    local_track_id: `s-fence-n#e2e-${sent}`,
    source: 'sim',
  }
  await json(await api.post(`${API}/events`, { headers, data: { events: [event] } }))
  await page.waitForFunction(() => window.cardSeenAt !== undefined, null, { timeout: 10_000 })
  const latency = (await page.evaluate(() => window.cardSeenAt ?? 0)) - sent

  test.info().annotations.push({ type: 'latency', description: `${latency} ms` })
  console.log(`event ingest → alert card: ${latency} ms (budget ${BUDGET_MS} ms)`)
  await test.info().attach('console', { body: await page.screenshot(), contentType: 'image/png' })
  expect(latency).toBeLessThanOrEqual(BUDGET_MS)
  await expect(page.locator(CARD)).toBeVisible()
  await api.dispose()
})
