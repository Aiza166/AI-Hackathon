import { apiCall, apiLogin, expect, fillWizard, openAs, resetDemo, sendClaim, shot, test } from './helpers'

// Journey 6: offline outbox. Go offline, send the claim, see the "waiting to send" strip,
// sign-out warns about the unsent claim, go online, the claim syncs exactly once.

test.describe('J6 Offline outbox', () => {
  test.beforeEach(async ({ request }) => {
    await resetDemo(request)
  })

  test('queued offline, sign-out confirm, synced exactly once', async ({ page, context, request }) => {
    const z = await apiLogin(request, 'zainab')
    await openAs(page, z)
    const posts: number[] = []
    page.on('response', (r) => {
      if (r.url().endsWith('/api/v1/cases') && r.request().method() === 'POST') posts.push(r.status())
    })

    // Fill online (drafts are saved on the phone as she goes), then the signal drops.
    await fillWizard(page, { dob: '1962-06-01', useDemoButton: true })
    await context.setOffline(true)
    await sendClaim(page)

    const strip = page.locator('.outbox')
    await expect(strip).toContainText('1 claim is saved on this phone, waiting to send.')
    await expect(strip).toContainText('No signal right now')
    await shot(page, 'j6-01-queued-offline')

    // Sign out with an unsent claim: in-page confirm, stay signed in
    await page.getByRole('button', { name: /Sign out/ }).click()
    await expect(page.getByRole('alertdialog')).toContainText('1 claim not sent yet. Signing out deletes it.')
    await shot(page, 'j6-02-signout-confirm')
    await page.getByRole('button', { name: /Stay signed in/ }).click()
    await expect(page.getByRole('alertdialog')).toHaveCount(0)

    // Reload while offline: the queued claim survives (IndexedDB)
    // (skipped on the dev server: a reload offline cannot fetch the app shell without the service worker)

    // Back online: sends by itself
    await context.setOffline(false)
    await expect(strip).toHaveCount(0, { timeout: 60_000 })
    await expect(page.locator('.claim-item')).toHaveCount(1, { timeout: 30_000 })

    // Flip the connection again: nothing is re-sent
    await context.setOffline(true)
    await context.setOffline(false)
    await page.waitForTimeout(3_000)
    const cases = (await apiCall<any[]>(request, z, 'GET', '/api/v1/cases')).body.data
    test.info().annotations.push({ type: 'sync', description: `server cases=${cases.length}, POST statuses=${posts.join(',')}` })
    expect(cases.length, 'exactly one claim on the server').toBe(1)
    expect(posts.filter((s) => s === 201).length).toBe(1)
    await shot(page, 'j6-03-synced')

    // Sign out now has nothing unsent: no confirm
    await page.getByRole('button', { name: /Sign out/ }).click()
    await expect(page.getByRole('button', { name: 'Demo accounts (mock)' })).toBeVisible()
  })

  test('same Idempotency-Key replayed returns the same case, not a second one', async ({ request }) => {
    const z = await apiLogin(request, 'zainab')
    const body = {
      claimant_cnic: '9000000000022', claimant_name: 'Zainab Bibi', claimant_dob: '1962-06-01', relation_claimed: 'widow',
      deceased_cnic: '9000000000011', deceased_name: 'Muhammad Aslam', payout_iban: 'PK00MOCK0000000000000001', documents: ['death_certificate'],
    }
    const key = `e2e-${Date.now()}`
    const headers = { Authorization: `Bearer ${z.token}`, 'Idempotency-Key': key }
    const a = await request.post('/api/v1/cases', { data: body, headers })
    const b = await request.post('/api/v1/cases', { data: body, headers })
    const ida = (await a.json()).data?.id
    const idb = (await b.json()).data?.id
    test.info().annotations.push({ type: 'idempotency', description: `${a.status()} ${b.status()} same=${ida === idb}` })
    expect(a.status()).toBe(201)
    expect([200, 201]).toContain(b.status())
    expect(idb).toBe(ida)
  })
})
