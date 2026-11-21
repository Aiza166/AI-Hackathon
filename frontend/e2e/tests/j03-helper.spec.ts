import { apiCall, apiLogin, expect, openAs, resetDemo, shot, test, zainabClaim } from './helpers'

// Journey 3: Helper Mode. Family picker, locked families, "now acting for" banner,
// and the helper can start a payout change but cannot confirm it with a PIN (UI + API).

test.describe('J3 Helper mode', () => {
  test.beforeEach(async ({ request }) => {
    await resetDemo(request)
  })

  test('family picker, locked family, acting-for banner, no PIN box, API refuses helper confirm', async ({ page, request }) => {
    const z = await apiLogin(request, 'zainab')
    const created = await apiCall<any>(request, z, 'POST', '/api/v1/cases', zainabClaim('1962-06-01'))
    expect(created.status).toBe(201)

    // The seed has one locked family (Mehrunnisa took back access); also lock Zainab by taking access back.
    const seeded = (await apiCall<any[]>(request, await apiLogin(request, 'ayesha'), 'GET', '/api/v1/helper/families')).body.data
    expect(seeded.filter((f: any) => f.consent_active === false).map((f: any) => f.name)).toEqual(['Mehrunnisa'])
    const consents = (await apiCall<any>(request, z, 'GET', '/api/v1/me/consents')).body.data.consents
    const helperConsent = consents.find((c: any) => c.grantee_type === 'helper' && c.status === 'active')
    expect((await apiCall(request, z, 'POST', `/api/v1/me/consents/${helperConsent.id}/withdraw`, {})).status).toBe(200)

    const ayesha = await apiLogin(request, 'ayesha')
    const fams = (await apiCall<any[]>(request, ayesha, 'GET', '/api/v1/helper/families')).body.data
    const locked = fams.filter((f) => f.consent_active === false || !f.cnic)
    test.info().annotations.push({ type: 'families', description: `${fams.length} families, ${locked.length} locked after Zainab withdrew` })
    expect(fams.length).toBeGreaterThanOrEqual(10)
    expect(locked.map((f) => f.name)).toContain('Zainab Bibi')
    expect(locked.every((f) => !f.cnic), 'locked families hide the CNIC').toBeTruthy()

    await openAs(page, ayesha)
    await expect(page.getByRole('heading', { name: /Families \(\d+\)/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /Start a new pension claim/ })).toBeDisabled()
    await page.getByPlaceholder('Search by name').fill('Zainab')
    await page.getByRole('button', { name: /Zainab Bibi/ }).click()
    await expect(page.getByText(/has not given you consent/)).toBeVisible()
    await expect(page.getByRole('button', { name: /Start a new pension claim/ })).toBeDisabled()
    await expect(page.getByRole('button', { name: /Change payout account/ })).toBeDisabled()
    await shot(page, 'j3-01-locked-family')

    // Zainab shares again; the helper reloads
    const grant = await apiCall(request, z, 'POST', '/api/v1/me/consents', { grantee_type: 'helper', grantee_id: helperConsent.grantee_id, fields: helperConsent.fields })
    expect(grant.status).toBe(201)
    await page.reload()
    await expect(page.getByRole('heading', { name: /Families \(\d+\)/ })).toBeVisible()

    // Zainab: acting-for banner
    await page.getByPlaceholder('Search by name').fill('Zainab')
    await page.getByRole('button', { name: /Zainab Bibi/ }).click()
    await expect(page.locator('.acting')).toContainText('Now acting for: Zainab Bibi')
    await expect(page.getByRole('button', { name: /Start a new pension claim/ })).toBeEnabled()
    await shot(page, 'j3-02-acting-for')

    // SafeSwitch as helper: can start, cannot confirm
    await page.getByRole('button', { name: /Change payout account/ }).click()
    await expect(page.locator('.acting')).toContainText('Zainab Bibi')
    await page.getByRole('button', { name: 'Demo: Own wallet' }).click()
    await page.getByRole('button', { name: /Check account and request change/ }).click()
    await expect(page.getByText(/Only Zainab Bibi can confirm this/)).toBeVisible()
    await expect(page.getByRole('button', { name: /Confirm with my PIN/ })).toHaveCount(0)
    await shot(page, 'j3-03-helper-no-pin')

    const changes = await apiCall<any[]>(request, ayesha, 'GET', `/api/v1/cases/${created.body.data.id}/payout-changes`)
    const change = changes.body.data[0]
    const confirm = await apiCall(request, ayesha, 'POST', `/api/v1/payout-changes/${change.id}/confirm`, { pin: '1234' })
    expect(confirm.status, 'helper confirm with PIN must be refused').toBe(403)
  })

  test('citizen token cannot call officer approve endpoint (403)', async ({ request }) => {
    const z = await apiLogin(request, 'zainab')
    const created = await apiCall<any>(request, z, 'POST', '/api/v1/cases', zainabClaim(null))
    const res = await apiCall(request, z, 'POST', `/api/v1/cases/${created.body.data.id}/approve`, { reason: 'self approve' })
    expect(res.status).toBe(403)
  })
})
