import { expect, test } from './helpers'

// Journey 10: rough first render on "Slow 3G" (CDP throttling) against the PRODUCTION build
// served by `vite preview` (E2E_PREVIEW_URL, localhost only), plus bytes on the wire.
// Bundle sizes come from `npm run build` output (see docs/TEST-REPORT.md).

const PREVIEW = process.env.E2E_PREVIEW_URL ?? 'http://localhost:5181'
const SLOW_3G = { offline: false, latency: 400, downloadThroughput: (400 * 1000) / 8, uploadThroughput: (400 * 1000) / 8 }

test.describe('J10 Performance (production build)', () => {
  test.skip(!/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(PREVIEW), 'localhost only')

  test('cold load on Slow 3G: time to first render and bytes', async ({ page, context }) => {
    const cdp = await context.newCDPSession(page)
    await cdp.send('Network.enable')
    await cdp.send('Network.setCacheDisabled', { cacheDisabled: true })
    await cdp.send('Network.emulateNetworkConditions', SLOW_3G)
    let bytes = 0
    cdp.on('Network.loadingFinished', (e: { encodedDataLength: number }) => {
      bytes += e.encodedDataLength
    })

    const t0 = Date.now()
    await page.goto(PREVIEW, { waitUntil: 'commit' })
    await expect(page.getByRole('heading', { name: /Sahara/ })).toBeVisible({ timeout: 60_000 })
    const firstRenderMs = Date.now() - t0
    const fcp = await page.evaluate(() => performance.getEntriesByName('first-contentful-paint')[0]?.startTime ?? null)
    const bytesAtRender = bytes
    // Let the service worker precache run, then count everything downloaded on the first visit
    await page.waitForTimeout(20_000)
    const swCount = await page.evaluate(async () => (await navigator.serviceWorker?.getRegistrations())?.length ?? 0)
    test.info().annotations.push({
      type: 'slow3g',
      description: JSON.stringify({ firstRenderMs, fcpMs: fcp && Math.round(fcp), kbAtRender: Math.round(bytesAtRender / 1024), kbAfter20s: Math.round(bytes / 1024), serviceWorkers: swCount }),
    })
    expect.soft(firstRenderMs, 'first render on Slow 3G under 10 s').toBeLessThan(10_000)
  })

  test('service worker: app shell reloads with no signal, saved draft survives', async ({ page, context, request }) => {
    await page.goto(PREVIEW)
    await page.waitForFunction(async () => Boolean((await navigator.serviceWorker.ready).active), null, { timeout: 30_000 })
    await page.reload() // now controlled by the service worker
    await page.getByRole('button', { name: 'Demo accounts (mock)' }).click()
    await page.getByRole('button', { name: /Zainab/ }).click()
    await page.getByRole('button', { name: /Start a new pension claim/ }).click()
    await page.getByRole('button', { name: /Next/ }).click()
    await page.locator('input[type="date"]').fill('1962-06-01')
    await page.getByRole('button', { name: /Next/ }).click()
    await expect(page.getByText('3 / 7')).toBeVisible()
    await expect(page.getByText('Saved on this phone')).toBeVisible()
    await context.setOffline(true)
    await page.reload()
    const shellOk = await page.locator('.prototype-banner').isVisible({ timeout: 15_000 }).catch(() => false)
    await page.getByRole('button', { name: /Start a new pension claim/ }).click({ timeout: 10_000 }).catch(() => undefined)
    const resumedAt = await page.locator('.wizard-count').textContent({ timeout: 10_000 }).catch(() => null)
    test.info().annotations.push({ type: 'offline-reload', description: JSON.stringify({ shellOk, resumedAt }) })
    await context.setOffline(false)
    expect(shellOk, 'app shell loads offline from the service worker').toBeTruthy()
    expect.soft(resumedAt, 'wizard resumes at the saved step after an offline reload').toBe('3 / 7')
  })
})
